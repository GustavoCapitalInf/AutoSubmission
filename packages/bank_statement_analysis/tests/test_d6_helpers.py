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


from analysis.transaction_classifier import (  # noqa: E402
    _leading_payee_words,
    _originator_segment,
    _payee_region,
    _row_before_receiver,
    _unknown_payee_tokens,
)


def test_the_payee_region_drops_the_originator_label_and_stops_at_the_first_ach_field():
    text = normalize("Orig CO Name:Fabricated Widgets Orig ID:0000 Desc Date: CO Entry Descr:Payment")
    assert _payee_region(text).split() == ["FABRICATED", "WIDGETS"]


def test_the_row_before_the_receiver_keeps_the_entry_description_and_drops_the_holder():
    text = normalize("FAB SCHOOL DES:FACTS ID:0001 INDN:PAT EXAMPLE CO ID:0002 WEB")
    assert _row_before_receiver(text).split() == ["FAB", "SCHOOL", "DES", "FACTS", "ID", "0001"]
    assert _row_before_receiver("NO RECEIVER FIELD HERE") == "NO RECEIVER FIELD HERE"


@pytest.mark.parametrize(
    ("printed", "leading"),
    [
        ("PRE-AUTHORIZED PAYMENT FIDO MOBILE PAP", "FIDO MOBILE PAP"),
        ("ONLINE BANKING PAYMENT 1234 ROGERS WIRELESS", "ROGERS WIRELESS"),
        ("ELECTRONIC WITHDRAWAL TO ATT", "ATT"),
        ("RECURRING PAYMENT AUTHORIZED ON 01/05 VZWRLSS*APOCC VISB CARD 1234", "VZWRLSS APOCC VISB CARD"),
        ("ACH CORP DEBIT 00012345 FAB PARTNERS LLC BOOST MOBILE CUSTOMER ID 1", "CORP DEBIT"),
    ],
)
def test_the_leading_payee_words_skip_channel_and_prefix_words_and_stop_at_a_reference(printed, leading):
    assert _leading_payee_words(normalize(printed)) == leading


@pytest.mark.parametrize(
    ("printed", "segment"),
    [
        ("ACH DEBIT DATAPAY IN 1234 C 5678 BILLING 9", "ACH DEBIT DATAPAY IN"),
        ("PATRIOT SOFTWARE DES:PAYROLLTAX ID:0001 INDN:FAB HOLDER CO ID:0002 CCD", "PATRIOT SOFTWARE"),
        ("FABRIKAM FUNDER DES:PAYMENT ID:0001 INDN:TASC BUILDERS INC CO ID:0002 CCD", "FABRIKAM FUNDER"),
        # Wells Fargo's label-less form: the holder follows the date, which ends the originator.
        ("FABRIKAM FUNDER DEBIT CCD 0105 TASC BUILDERS INC", "FABRIKAM FUNDER DEBIT CCD"),
    ],
)
def test_the_originator_segment_never_reads_a_receiver_field(printed, segment):
    assert _originator_segment(normalize(printed)).split() == segment.split()


def test_the_d11_payee_words_are_unchanged_by_the_refactor():
    assert _unknown_payee_tokens(normalize("ACH DEBIT FABRICATED WIDGETS LLC 0001")) == ("FABRICATED", "WIDGETS", "LLC")
    assert _unknown_payee_tokens(normalize("FAB WIDGETS DES:PAYMENT ID:0001 INDN:PAT EXAMPLE")) == ("FAB", "WIDGETS")

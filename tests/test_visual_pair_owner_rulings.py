"""Fabricated inputs only. Gustavo's rulings of 2026-09-22:
1. a statement that prints no currency is USD unless the bank is Canadian;
2. the reviewer prompt defines bank, account_name and cheque-image pages, and never adds a cheque as a row;
3. a cut-off read holds its page (covered in tests/test_visual_pair_adversarial.py).
"""
from copy import deepcopy
from decimal import Decimal

from vlm import prompts
from vlm.assemble import CandidateRow
from vlm.currency import USD_DEFAULT_RULING, canadian_evidence, currency_resolution_manifest, usd_default
from vlm.pair import ledger_rows
from vlm.pair_metadata import merge_metadata
from vlm.review import PageReviewMerge


# --- 1. currency ---------------------------------------------------------------------------------------

def test_a_us_statement_without_printed_currency_defaults_to_usd_as_a_schema_default():
    result = usd_default("FABRICATED NATIONAL BANK", ["FABRICATED CO\n100 MAIN ST\nANYTOWN MN 55555"])
    assert result == {"ruling": USD_DEFAULT_RULING, "canadian_evidence": [],
                      "currency": "USD", "currency_source": "schema_default"}


def test_a_canadian_institution_name_blocks_the_default():
    for bank in ("TD Canada Trust", "Royal Bank of Canada", "RBC", "CIBC", "Scotiabank", "Desjardins",
                 "Banque Nationale", "BMO"):
        result = usd_default(bank, [])
        assert result["currency"] is None and result["canadian_evidence"] == ["canadian_institution_name"], bank


def test_a_canadian_address_blocks_the_default_whatever_the_bank_is_called():
    result = usd_default("FABRICATED TRUST", ["FABRICATED INC.\nFABRICATED CITY QC H0H 0H0"])
    assert result["currency"] is None and result["canadian_evidence"] == ["canadian_address"]
    assert canadian_evidence(None, ["FABRICATED CITY, ON K1A 0B1"]) == ("canadian_address",)


def test_california_and_postal_lookalikes_without_a_province_are_not_canadian():
    assert canadian_evidence(None, ["ANYTOWN CA 90000-0000"]) == ()
    assert canadian_evidence(None, ["REF A1B 2C3 TRANSFER"]) == ()          # no province before it


def test_canada_inside_a_transaction_description_is_not_evidence():
    # Page text is scanned for Canadian ADDRESSES only; a US card purchase can say AIR CANADA.
    assert canadian_evidence("FABRICATED NATIONAL BANK", ["POS PURCHASE AIR CANADA 123.45"]) == ()


def test_the_ruling_is_pinned_in_the_currency_manifest(monkeypatch):
    import vlm.currency as currency
    monkeypatch.setattr(currency, "registry_fingerprint", lambda: "fixed")
    owner = currency_resolution_manifest()["owner_default"]
    assert owner["ruling"] == USD_DEFAULT_RULING and owner["currency_source"] == "schema_default"


# --- 2. prompts ----------------------------------------------------------------------------------------

def test_both_reviewer_modes_define_bank_account_name_and_cheque_pages():
    review = prompts.stage_b_review_prompt([], page_number=1, page_total=1)
    discovery = prompts.STAGE_B_DISCOVERY_PROMPT
    for text in (review, discovery):
        assert "bank is the institution that issued the statement" in text
        assert "account_name is the account's own title or product name" in text
        assert "never the holder's name" in text
        assert '"cheque_images" if it shows only pictures of cheques' in text
        assert "Never add a transaction from a picture of a cheque" in text
    assert prompts.PROMPT_VERSION == 9


# --- 2b. the deterministic backstop for cheque-image pages -----------------------------------------------

def _page(number, *, role="statement_page", account=None, rows=1):
    body = tuple(CandidateRow("2031-01-02", "01/02", "FABRICATED ROW", Decimal("1.00"), "credit", None,
                              number, "stage_b", f"added{index}") for index in range(rows))
    base = {"period_start": "2031-01-01", "period_end": "2031-01-31", "currency": "USD",
            "account_number": "9-000-1111-2222"} if number == 1 else {}
    base.update(account or {})
    return PageReviewMerge(number, body, (), {"added": len(body)}, (), base, (), role, ())


def test_rows_on_cheque_image_pages_never_enter_the_ledger():
    rows, excluded = ledger_rows([_page(1, rows=3), _page(2, role="cheque_images", rows=6), _page(3, rows=2)])
    assert len(rows) == 5 and excluded == 6
    assert {row.page for row in rows} == {1, 3}


def test_a_cheque_pages_other_account_and_names_are_kept_but_never_compared():
    pages = [_page(1), _page(2, role="cheque_images",
                           account={"account_number": "7-000-3333-4444", "bank": "OTHER FABRICATED BANK",
                                    "account_name": "SOMEONE ELSE"})]
    before = deepcopy(pages)
    account, _, reasons, provenance = merge_metadata(pages)
    assert pages == before
    assert reasons == [] and account["account_number"] == "9-000-1111-2222"
    assert {"field": "account_number", "page": 2, "source": "reviewer", "value": "7-000-3333-4444"} in provenance

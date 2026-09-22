"""Fabricated inputs only. Gustavo's rulings of 2026-09-22:
1. a statement that prints no currency is USD unless the bank is Canadian;
2. the reviewer prompt defines bank, account_name and cheque-image pages, and never adds a cheque as a row;
3. a cut-off read holds its page (covered in tests/test_visual_pair_adversarial.py), except a cheque picture page,
   which nothing holds (ruling of the same day, "dont hold cheque picture pages").
"""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal

from vlm import prompts
from vlm.assemble import CandidateRow
from vlm.currency import USD_DEFAULT_RULING, canadian_evidence, currency_resolution_manifest, usd_default
from ocr.truncation import assess_pages
from vlm.pair import held_pages, ledger_rows, page_texts
from vlm.pair_metadata import merge_metadata
from vlm.review import PageReviewMerge, confidence_summary, mark_ledger_echoes


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


def _marked(*pages):
    # A labelled page's rows make it pictures only when they repeat earlier ledger transactions
    # (tests/test_visual_pair_cheque_echo.py); every fixture row here is 1.00.
    return mark_ledger_echoes(list(pages))


def test_rows_on_cheque_image_pages_never_enter_the_ledger():
    rows, excluded = ledger_rows(_marked(_page(1, rows=6), _page(2, role="cheque_images", rows=6), _page(3, rows=2)))
    assert len(rows) == 8 and excluded == 6
    assert {row.page for row in rows} == {1, 3}


def test_a_cheque_pages_other_account_and_names_are_kept_but_never_compared():
    pages = _marked(_page(1), _page(2, role="cheque_images",
                                    account={"account_number": "7-000-3333-4444", "bank": "OTHER FABRICATED BANK",
                                             "account_name": "SOMEONE ELSE"}))
    before = deepcopy(pages)
    account, _, reasons, provenance = merge_metadata(pages)
    assert pages == before
    assert reasons == [] and account["account_number"] == "9-000-1111-2222"
    assert {"field": "account_number", "page": 2, "source": "reviewer", "value": "7-000-3333-4444"} in provenance


# --- 3b. ruling, 2026-09-22: "dont hold cheque picture pages" ------------------------------------------------

def _held(pages, *, page_errors=None, truncated=None):
    return held_pages(pages, page_errors or [[] for _ in pages], truncated or [False for _ in pages])


def test_a_cut_off_read_of_a_cheque_picture_page_does_not_hold_it():
    pages = _marked(_page(1, rows=6), _page(2, role="cheque_images", rows=6))
    assert _held(pages, truncated=[False, True]) == []


def test_nothing_else_on_a_cheque_picture_page_holds_it_either():
    cheque = replace(_page(2, role="cheque_images", rows=6), counts={"added": 5, "unresolved": 1},
                     metadata_evidence=({"scope": "daily_balances", "page": 2},))
    assert _held(_marked(_page(1, rows=6), cheque), page_errors=[[], ["proposer_transport_failed"]]) == []


def test_a_cut_off_statement_page_still_holds():
    assert _held([_page(1), _page(2)], truncated=[False, True]) == [2]


def test_an_invalid_review_cannot_make_a_page_a_cheque_picture_page():
    # A review that failed validation cannot be trusted to say what the page shows.
    broken = replace(_page(2, role="cheque_images"), errors=("review_missing_candidate_id",))
    assert _held([_page(1), broken], page_errors=[[], ["review_missing_candidate_id"]], truncated=[False, True]) == [2]


def test_a_cheque_picture_page_is_out_of_the_confidence_counts_and_admission():
    cheque = replace(_page(2, role="cheque_images", rows=6), counts={"added": 5, "unresolved": 1})
    summary = confidence_summary(_marked(_page(1, rows=6), cheque), gate_admitted=True)
    assert summary["gate_admitted"] is True
    assert summary["counts"]["unresolved"] == 0 and summary["counts"]["added"] == 6
    assert summary["page_count"] == 2
    assert [page["cheque_pictures"] for page in summary["pages"]] == [False, True]


def test_a_cheque_picture_page_gives_the_bank_reader_no_text_and_is_never_a_truncated_page():
    cheque = _page(2, role="cheque_images", rows=6, account={"account_number": "7-000-3333-4444"})
    texts = page_texts(_marked(_page(1, rows=6), cheque), [True, True])
    assert texts[1] == "" and texts[1].finish_reason == "stop"
    assert texts[0].finish_reason == "length" and "FABRICATED ROW" in texts[0]
    assert [item.truncated for item in assess_pages(texts)] == [True, False]


def test_an_invalid_review_labelled_cheque_images_keeps_its_text_and_its_truncation():
    broken = replace(_page(2, role="cheque_images"), errors=("review_missing_candidate_id",))
    texts = page_texts([_page(1), broken], [False, True])
    assert texts[1].finish_reason == "length" and "FABRICATED ROW" in texts[1]


def test_a_page_printing_statement_summary_figures_is_not_a_cheque_picture_page():
    for name, value in (("beginning_balance", 145), ("ending_balance", 160), ("stated_total_credits", 20),
                        ("stated_debit_count", 1)):
        labelled = _page(2, role="cheque_images", rows=2, account={name: value})
        assert _held([_page(1), labelled], truncated=[False, True]) == [2], name
        rows, excluded = ledger_rows([_page(1), labelled])
        assert excluded == 0 and len(rows) == 3, name
        assert page_texts([_page(1), labelled], [False, True])[1].finish_reason == "length", name
    # Header details a cheque-image page repeats (bank, account, period) do not disqualify it.
    header = _page(2, role="cheque_images", rows=2, account={"bank": "FABRICATED BANK", "period_end": "2031-01-31"})
    assert _held(_marked(_page(1, rows=2), header), truncated=[False, True]) == []


def test_a_labelled_page_with_a_summary_box_has_its_metadata_compared():
    labelled = _page(2, role="cheque_images", account={"ending_balance": 160, "account_number": "7-000-3333-4444"})
    _, _, reasons, _ = merge_metadata([_page(1), labelled])
    assert reasons  # the other account number is compared, and conflicts


def test_a_labelled_page_is_pictures_only_when_its_kept_rows_repeat_the_ledger():
    # Third review finding on b4eea02: a real page labelled cheque_images with its summary box unread but its
    # proposed rows confirmed or corrected must count. The cheque-echo backstop decides by the rows themselves:
    # rows new to the statement make it a statement page; rows repeating earlier transactions make it
    # pictures, whether the proposer read them (confirmed, corrected) or only the reviewer added them.
    for state in ("agreed", "corrected", "added"):
        page = replace(_page(2, role="cheque_images", rows=2), counts={state: 2})
        new = _marked(_page(1), page)                  # one earlier 1.00 transaction for two rows
        assert _held(new, truncated=[False, True]) == [2], state
        rows, excluded = ledger_rows(new)
        assert excluded == 0 and len(rows) == 3, state
        echoed = _marked(_page(1, rows=2), page)       # two earlier 1.00 transactions
        assert _held(echoed, truncated=[False, True]) == [], state

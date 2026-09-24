"""Adversarial synthetic two-page receipts and whole-document admission checks."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from ocr.visual_pair_config import PROPOSER_REVISION, REVIEWER_REVISION
from vlm.client import ChatResult, TransportError
from vlm.receipts import canonical_json, sha256_bytes
from vlm.render import RenderedPage
from vlm.schema import empty_review


def _layout(page):
    cells = ("2031-01-02", "PAYROLL EXACT 01", "20.00", "", "120.00") if page == 0 else (
        "2031-01-03", "POS EXACT 02", "", "5.00", "115.00")
    header = "<tr>" + "".join(f"<th>{v}</th>" for v in ("Date", "Description", "Credit", "Debit", "Balance")) + "</tr>"
    row = "<tr>" + "".join(f"<td>{v}</td>" for v in cells) + "</tr>"
    # The proposer reads the whole page, so the figures each page's review reports are printed in its reading.
    figures = "Summary figures 100.00 31" if page == 0 else "Summary figures 115.00 20.00 5.00 1 0.00 0 114.00"
    return [{"bbox": [0, 0, 100, 100], "category": "Table", "text": "<table>" + header + row + "</table>"},
            {"bbox": [0, 0, 100, 100], "category": "Text", "text": figures}]


def _review(page):
    result = empty_review("statement_page")
    result["account"].update(bank="Synthetic Bank", account_number="123456", currency="USD",
                             period_start="2031-01-01", period_end="2031-01-31")
    if page == 0:
        result["account"].update(beginning_balance=100, account_name="Fabricated Account", days_in_period=31)
    else:
        result["account"].update(ending_balance=115, stated_total_credits=20, stated_total_debits=5,
            stated_credit_count=1, stated_debit_count=1, stated_service_charge=0,
            stated_interest_paid=0, stated_nsf_count=0, bank_reported_average_balance=114,
            bank_reported_average_label="Average ledger balance")
    result["account_numbers_seen"] = ["123456"]
    result["reviews"] = [{"candidate_id": f"p{page+1}r0", "verdict": "confirm",
                          "observed_description": "PAYROLL EXACT 01" if page == 0 else "POS EXACT 02",
                          "corrections": [], "reason": ""}]
    result["daily_balances"] = [{"date": f"2031-01-0{page+2}", "balance": 120 if page == 0 else 115}]
    return result


@pytest.fixture
def pair_two_pages(tmp_path, monkeypatch):
    import vlm.pair as pair
    import vlm.render as renderer
    # Stable fixture identity prevents unrelated concurrent source edits from
    # changing a receipt key while these synthetic tests exercise restoration.
    monkeypatch.setattr(pair, "visual_pair_manifest", lambda: {"test_contract": 1})
    pdf = tmp_path / "fabricated.pdf"
    pdf.write_bytes(b"%PDF synthetic only")
    pages = [RenderedPage(i, 100, 100, f"image{i}".encode(), sha256_bytes(f"image{i}".encode()),
                          "pixels", 72, 72, 0, 0, 0) for i in range(2)]
    monkeypatch.setattr(renderer, "render_pages", lambda *a, **k: pages)
    state = SimpleNamespace(calls=[], layouts=[_layout(0), _layout(1)], reviews=[_review(0), _review(1)],
                            failures=set(), truncated=set(), created=100)
    class Client:
        def __init__(self, url, **kwargs):
            self.stage = "proposer" if "18013" in url else "reviewer"
        def get_json(self, path):
            revision = PROPOSER_REVISION if self.stage == "proposer" else REVIEWER_REVISION
            model = "dotsmocr" if self.stage == "proposer" else "qwen3.8-27b-nvfp4"
            return {"data": [{"id": model, "root": "/snapshots/" + revision, "created": state.created}]}
        def chat(self, model, prompt, **kwargs):
            page = int(kwargs["image_jpeg"][-1:])
            state.calls.append((self.stage, page))
            if (self.stage, page) in state.failures:
                raise TransportError("connection_failed")
            obj = state.layouts[page] if self.stage == "proposer" else state.reviews[page]
            text = canonical_json(obj)
            finish = "length" if (self.stage, page) in state.truncated else "stop"
            request = canonical_json({"model": model, "prompt": prompt, "image": page}).encode()
            raw = canonical_json({"choices": [{"message": {"content": text}, "finish_reason": finish}],
                                  "usage": {"prompt_tokens": 10, "completion_tokens": 30}}).encode()
            return ChatResult(text, None if self.stage == "proposer" else deepcopy(obj), None,
                              finish, 10, 30, 1, sha256_bytes(request), sha256_bytes(raw),
                              sha256_bytes(text.encode()), request, raw)
    monkeypatch.setattr(pair, "VlmClient", Client)
    return pair, pdf, tmp_path / "evidence", state


def _extract(fixture, **kwargs):
    pair, pdf, directory, _ = fixture
    return pair.extract_visual_pair(pdf, evidence_dir=directory, data_scope="synthetic", **kwargs)


def test_two_pages_preserve_optional_source_fields_and_daily_ledger(pair_two_pages):
    doc = _extract(pair_two_pages)
    assert len(doc.pages) == len(doc.page_integrity) == len(doc.page_extractor) == 2
    assert doc.visual_pair["gate"]["admitted"]
    statement = doc.visual_pair["statement"]
    expected = {"account_name": "Fabricated Account", "account_number": "123456", "days_in_period": 31,
        "stated_service_charge": 0, "stated_interest_paid": 0, "stated_nsf_count": 0,
        "bank_reported_average_balance": 114, "bank_reported_average_label": "Average ledger balance"}
    assert {key: statement[key] for key in expected} == expected
    assert statement["stated_daily_balances"] == [{"date": "2031-01-02", "balance": 120}, {"date": "2031-01-03", "balance": 115}]
    assert [row["description"] for row in statement["transactions"]] == ["PAYROLL EXACT 01", "POS EXACT 02"]


@pytest.mark.parametrize("field,value,reason", [
    ("currency", "CAD", "currency_conflict"), ("period_end", "2031-02-28", "period_mismatch"),
    ("beginning_balance", 200, "anchor_disagreement"), ("account_number", "993456", "proposal_invalid"),
])
def test_metadata_conflicts_never_admit_a_partial_statement(pair_two_pages, field, value, reason):
    pair_two_pages[3].reviews[1]["account"][field] = value
    if field == "beginning_balance":  # a figure conflict is two PRINTED figures (see the next test)
        pair_two_pages[3].layouts[1][1]["text"] += " 200.00"
    doc = _extract(pair_two_pages)
    assert reason in doc.visual_pair["gate"]["reasons"]
    assert not doc.visual_pair["gate"]["admitted"]
    assert doc.visual_pair["statement"] is None
    assert len(doc.pages) == 2


def test_a_conflicting_figure_printed_nowhere_is_dropped_not_held(pair_two_pages):
    # The reviewer reports a figure the page does not print (neither its text layer nor the proposer's reading):
    # it is not evidence, so it neither contradicts the printed figures nor holds the statement.
    pair_two_pages[3].reviews[1]["account"]["beginning_balance"] = 200
    doc = _extract(pair_two_pages)
    assert doc.visual_pair["gate"]["admitted"]
    assert {"scope": "account", "page": 2, "field": "beginning_balance",
            "code": "review_figure_not_printed"} in doc.visual_pair["review_diagnostics"]


def test_cross_page_daily_balance_conflict_is_refused(pair_two_pages):
    pair_two_pages[3].reviews[1]["daily_balances"].append({"date": "2031-01-02", "balance": 900})
    pair_two_pages[3].layouts[1][1]["text"] += " 900.00"
    doc = _extract(pair_two_pages)
    assert "anchor_disagreement" in doc.visual_pair["gate"]["reasons"]
    assert doc.visual_pair["statement"] is None


@pytest.mark.parametrize("stage", ["proposer", "reviewer"])
def test_truncated_later_page_keeps_slot_and_cached_refusal(pair_two_pages, stage):
    state = pair_two_pages[3]
    state.truncated.add((stage, 1))
    doc = _extract(pair_two_pages)
    assert len(doc.pages) == 2 and doc.truncated_pages == [1]
    assert doc.visual_pair["statement"] is None
    assert not doc.visual_pair["gate"]["admitted"]
    before = list(state.calls)
    again = _extract(pair_two_pages)
    assert state.calls == before
    assert again.visual_pair == doc.visual_pair
    assert again.truncated_pages == [1]


@pytest.mark.parametrize("stage", ["proposer", "reviewer"])
def test_transport_failure_keeps_all_page_slots_and_is_cached_without_hidden_retry(pair_two_pages, stage):
    state = pair_two_pages[3]
    state.failures.add((stage, 0))
    doc = _extract(pair_two_pages)
    assert len(doc.pages) == 2
    assert f"{stage}_transport_failed" in doc.visual_pair["pages"][0]["errors"]
    assert not doc.visual_pair["gate"]["admitted"] and doc.visual_pair["statement"] is None
    assert state.calls == [("proposer", 0), ("proposer", 1), ("reviewer", 0), ("reviewer", 1)]
    _extract(pair_two_pages)
    assert len(state.calls) == 4


def test_interrupted_document_reuses_successful_pages(pair_two_pages):
    def interrupt(stage):
        if stage == "visual_pair_reviewing:1/2":
            raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        _extract(pair_two_pages, progress=interrupt)
    assert pair_two_pages[3].calls == [("proposer", 0), ("proposer", 1)]
    doc = _extract(pair_two_pages)
    assert doc.visual_pair["gate"]["admitted"]
    assert pair_two_pages[3].calls == [("proposer", 0), ("proposer", 1), ("reviewer", 0), ("reviewer", 1)]


def test_restart_attestation_changes_do_not_re_read_completed_pages(pair_two_pages):
    def interrupt(stage):
        if stage == "visual_pair_reviewing:1/2":
            raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        _extract(pair_two_pages, progress=interrupt)
    state = pair_two_pages[3]
    state.created += 1  # serving process restart; weights/config remain pinned.
    doc = _extract(pair_two_pages)
    assert doc.visual_pair["gate"]["admitted"]
    assert state.calls == [("proposer", 0), ("proposer", 1), ("reviewer", 0), ("reviewer", 1)]
    assert [row["stage"] for row in doc.extraction_telemetry["pages"]] == ["reviewer", "reviewer"]


def test_interrupted_failed_request_retains_refusal_without_automatic_retry(pair_two_pages):
    state = pair_two_pages[3]
    state.failures.add(("proposer", 0))
    def interrupt(stage):
        if stage == "visual_pair_reviewing:1/2":
            raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        _extract(pair_two_pages, progress=interrupt)
    assert state.calls == [("proposer", 0), ("proposer", 1)]
    state.failures.clear()  # A healthy server is not authorization to re-read.
    doc = _extract(pair_two_pages)
    assert state.calls == [("proposer", 0), ("proposer", 1), ("reviewer", 0), ("reviewer", 1)]
    assert "proposer_transport_failed" in doc.visual_pair["pages"][0]["errors"]
    assert doc.visual_pair["statement"] is None
    digest = doc.visual_pair["receipt_sha256"]
    receipt = json.loads((pair_two_pages[2] / "blobs" / digest[:2] / digest).read_text())
    assert len(receipt["failed_calls"]) == 1
    assert receipt["failed_calls"][0]["receipt_sha256"]


def test_changed_cached_call_refuses_without_re_read(pair_two_pages):
    def interrupt(stage):
        if stage == "visual_pair_reviewing:2/2":
            raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        _extract(pair_two_pages, progress=interrupt)
    directory = pair_two_pages[2]
    # Corrupt the saved parsed result while preserving original request/response
    # bytes. The call's content-addressed envelope must expose the divergence.
    pointer_path = next((directory / "calls").glob("*.json"))
    pointer = json.loads(pointer_path.read_text())
    digest = pointer["call_sha256"]
    blob_path = directory / "blobs" / digest[:2] / digest
    saved = json.loads(blob_path.read_text())
    saved["parsed"] = {"invented": "statement"}
    blob_path.write_text(canonical_json(saved))
    before = list(pair_two_pages[3].calls)
    with pytest.raises(pair_two_pages[0].VisualPairError, match="evidence_changed"):
        _extract(pair_two_pages)
    assert pair_two_pages[3].calls == before


def test_changed_completed_document_cache_refuses_without_re_read(pair_two_pages):
    _extract(pair_two_pages)
    directory = pair_two_pages[2]
    index = next(directory.glob("*.json"))
    record = json.loads(index.read_text())
    record["document"]["visual_pair"]["statement"]["transactions"][0]["amount"] = 999
    index.write_text(canonical_json(record))
    before = list(pair_two_pages[3].calls)
    with pytest.raises(pair_two_pages[0].VisualPairError, match="cache_changed"):
        _extract(pair_two_pages)
    assert pair_two_pages[3].calls == before


def test_pair_http_timeout_is_one_attempt_without_hidden_retry(monkeypatch):
    import urllib.error
    from vlm.pair import _client
    from vlm.client import TransportError
    attempts = []
    class Opener:
        def open(self, request, **kwargs):
            attempts.append(request)
            raise urllib.error.URLError(TimeoutError())
    monkeypatch.setattr("vlm.client._default_opener", lambda: Opener())
    client = _client("http://127.0.0.1:18013/v1", 1)
    with pytest.raises(TransportError, match="connection_failed"):
        client.chat("dotsmocr", "synthetic", image_jpeg=b"synthetic")
    assert len(attempts) == 1

"""O-3 truncation detection: the flag must fire on a cut-off page and must NOT
fire on anything the corpus actually contains.

Precision is the whole point — a flagged page routes to re-OCR or human review —
so the negative fixtures here carry as much weight as the positive one, and the
corpus tests at the bottom prove the detector is silent over every source text
the validated 109 documents produce.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest
from PIL import Image

from corpus_artifacts import DEFAULT_CACHE, manifest_entries
from ocr.config import Settings
from ocr.document import StatementMarkdown
from ocr.native_text import _native_pages
from ocr.ocr_client import ocr_page, postprocess
from ocr.pipeline import parse_statement
from ocr.truncation import (
    PageIntegrity,
    PageText,
    SIGNAL_FINISH_REASON,
    SIGNAL_OPEN_CELL,
    SIGNAL_OPEN_ROW,
    SIGNAL_OPEN_TABLE,
    SIGNAL_PARTIAL_TAG,
    SIGNAL_TOKEN_CEILING,
    assess_page,
    assess_pages,
    model_truncation_signals,
    structural_tail_signals,
)


# ---------------------------------------------------------------------------
# The dense-page fixture: a long transaction table, complete and cut off.
# ---------------------------------------------------------------------------

def _dense_rows(count: int) -> str:
    return "".join(
        f"<tr><td>03/{(i % 28) + 1:02d}</td>"
        f"<td>ONLINE TRANSFER TO CHECKING CONF# {700000 + i}</td>"
        f"<td>{i * 13 + 7}.{i % 100:02d}</td></tr>"
        for i in range(count)
    )


DENSE_PAGE_COMPLETE = (
    "STATEMENT OF ACCOUNT\n\n"
    "<table><tr><td>DATE</td><td>DESCRIPTION</td><td>AMOUNT</td></tr>"
    + _dense_rows(60)
    + "</table>\n\nPage 3 of 9"
)

# The same page as the model would leave it after hitting the token ceiling
# three quarters of the way down the ledger: mid-row, mid-cell, no closing tags.
DENSE_PAGE_TRUNCATED = (
    "STATEMENT OF ACCOUNT\n\n"
    "<table><tr><td>DATE</td><td>DESCRIPTION</td><td>AMOUNT</td></tr>"
    + _dense_rows(45)
    + "<tr><td>03/18</td><td>ONLINE TRANSFER TO CHECK"
)


# ---------------------------------------------------------------------------
# Model-side signals
# ---------------------------------------------------------------------------

def test_finish_reason_length_is_a_truncation_signal():
    assert model_truncation_signals("length") == [SIGNAL_FINISH_REASON]
    assert model_truncation_signals("max_tokens") == [SIGNAL_FINISH_REASON]
    assert model_truncation_signals("LENGTH") == [SIGNAL_FINISH_REASON]


def test_a_completed_or_unreported_generation_is_not_a_signal():
    assert model_truncation_signals("stop") == []
    assert model_truncation_signals(None) == []
    assert model_truncation_signals("") == []
    # A non-string (a mock, a dict) must never be read as truncation.
    assert model_truncation_signals(object()) == []


def test_usage_at_the_token_ceiling_is_a_signal_on_its_own():
    # Endpoints that report usage but no finish_reason still expose the ceiling.
    assert model_truncation_signals(None, 4096, 4096) == [SIGNAL_TOKEN_CEILING]
    assert model_truncation_signals(None, 4100, 4096) == [SIGNAL_TOKEN_CEILING]


def test_usage_below_the_ceiling_is_not_a_signal():
    assert model_truncation_signals("stop", 4095, 4096) == []
    assert model_truncation_signals("stop", None, 4096) == []
    assert model_truncation_signals("stop", 4096, None) == []
    assert model_truncation_signals("stop", 0, 0) == []


# ---------------------------------------------------------------------------
# Structural page-tail heuristics — positives
# ---------------------------------------------------------------------------

def test_dense_page_cut_mid_table_row_is_flagged():
    integrity = assess_page(DENSE_PAGE_TRUNCATED, page_index=2)
    assert integrity.truncated
    assert integrity.page_index == 2
    # every open structure at the tail is named, so review has the evidence
    assert integrity.signals == [SIGNAL_OPEN_TABLE, SIGNAL_OPEN_ROW, SIGNAL_OPEN_CELL]


def test_page_cut_inside_a_tag_is_flagged():
    cut = DENSE_PAGE_COMPLETE[: DENSE_PAGE_COMPLETE.rfind("<table>") + 400] + "</td></tr><t"
    assert SIGNAL_PARTIAL_TAG in structural_tail_signals(cut)


def test_page_cut_inside_a_model_special_token_is_flagged():
    # Generation stopped part-way through a "<|det|>" region marker, which the
    # postprocess strippers cannot remove because it never closed.
    assert SIGNAL_PARTIAL_TAG in structural_tail_signals(
        "<table><tr><td>03/19</td></tr></table>\nTotal 1,200.00 <|de"
    )


def test_each_open_structure_is_reported_independently():
    # Row closed cleanly but the table never was.
    assert structural_tail_signals("<table><tr><td>03/19</td></tr>") == [SIGNAL_OPEN_TABLE]
    # Cells closed, row left hanging.
    assert structural_tail_signals("<tr><td>03/19</td><td>DEPOSIT</td>") == [SIGNAL_OPEN_ROW]
    # Cut inside the cell contents.
    assert structural_tail_signals("<tr><td>03/19</td><td>DEPO") == [
        SIGNAL_OPEN_ROW, SIGNAL_OPEN_CELL,
    ]


# ---------------------------------------------------------------------------
# Structural page-tail heuristics — negatives (precision)
# ---------------------------------------------------------------------------

def test_complete_dense_page_is_not_flagged():
    assert structural_tail_signals(DENSE_PAGE_COMPLETE) == []
    assert not assess_page(DENSE_PAGE_COMPLETE).truncated


def test_page_with_several_closed_tables_is_not_flagged():
    page = (
        "<table><tr><td>Beginning Balance</td><td>11,982.22</td></tr></table>\n"
        "Deposits and other credits\n"
        "<table><tr><td>DATE</td><td>DESCRIPTION</td><td>AMOUNT</td></tr>"
        "<tr><td>03/19</td><td>DEBIT CARD FOOD LION</td><td>66.07</td></tr></table>\n"
        "<table><tr><td>Ending Balance</td><td>12,048.29</td></tr></table>"
    )
    assert structural_tail_signals(page) == []


def test_cells_with_attributes_do_not_confuse_the_tail_check():
    page = ('<table><tr><td colspan="3">Continued on next page</td></tr>'
            '<tr><th>DATE</th><th>AMOUNT</th></tr>'
            '<tr><td>03/19</td><td>66.07</td></tr></table>')
    assert structural_tail_signals(page) == []


def test_embedded_check_image_does_not_flag():
    page = ('<table><tr><td>03/19</td><td>CHECK 1041</td><td>250.00</td></tr></table>\n\n'
            '<img class="doc-image" src="data:image/png;base64,AAAA" alt="image" />')
    assert structural_tail_signals(page) == []


def test_native_text_pages_never_flag():
    # Plain extracted text: no markup, and the tail shapes that a lower-precision
    # heuristic would trip on (a bare amount, a footer, an unterminated line, a
    # less-than sign, a single-decimal rate).
    for page in (
        "NAVY FEDERAL CREDIT UNION\nBeginning Balance 11,982.22\nEnding Balance 12,048.29",
        "Statement Period 03/01/53 - 03/31/53\nPage 4 of 10",
        "Total withdrawals and other debits -$200.27",
        "Annual Percentage Yield Earned 0.5",
        "Overdraft applies when balance < 0",
        "TOTAL 1,234.5",
    ):
        assert structural_tail_signals(page) == [], page
        assert not assess_page(page).truncated


def test_empty_and_whitespace_pages_do_not_flag():
    assert structural_tail_signals("") == []
    assert structural_tail_signals("   \n\n  ") == []
    assert assess_pages(["", None, "   "]) == [
        PageIntegrity(page_index=0), PageIntegrity(page_index=1), PageIntegrity(page_index=2),
    ]


def test_postprocess_of_a_full_read_never_manufactures_a_signal():
    # The cleanup chain rebuilds tables (fused-header repair, amount-bleed fix,
    # det-tag stripping, image embedding). Whatever it does, a complete read must
    # come out balanced — otherwise the detector would flag clean pages.
    raw = (
        "<|det|>title [10, 10, 900, 40]<|/det|>STATEMENT OF ACCOUNT\n"
        "[Non-Text]\n"
        "<table><tr><td>DATE04/06</td><td>DESCRIPTIONOrig CO Name:Sq</td>"
        "<td>Orig ID:9424 Ind Name:Choudhri</td><td>AMOUNT260.00</td></tr>"
        "<tr><td>04/06</td><td>Payment Received</td><td>04/05 Lyft Card 0298</td>"
        "<td>235.17</td></tr></table>\n"
        "<|det|>footer [819, 811, 942, 825] Page 4 of 10 Page 4 of 10"
    )
    cleaned = postprocess(raw)
    assert "<table>" in cleaned  # the chain really did run over a table
    assert structural_tail_signals(cleaned) == []
    # Review MINOR-5: OQ1 = C means NOTHING calls `postprocess` on the
    # analysis path any more -- `assess_pages` sees the RAW completion, not
    # `cleaned`. The property this test exists to prove ("a complete read
    # never flags") must hold on the text the detector actually sees now,
    # not only on a text no production path produces any more.
    assert structural_tail_signals(raw) == []


# ---------------------------------------------------------------------------
# PageText — the model-signal carrier
# ---------------------------------------------------------------------------

def test_page_text_behaves_exactly_like_the_string_it_wraps():
    page = PageText("# markdown", finish_reason="stop", completion_tokens=120, max_tokens=4096)
    assert isinstance(page, str)
    assert page == "# markdown"
    assert page.strip() == "# markdown"
    assert [page] == ["# markdown"]
    assert str(page) == "# markdown" and type(str(page)) is str


def test_page_text_defaults_report_no_model_signals():
    page = PageText("# markdown")
    assert page.finish_reason is None
    assert page.completion_tokens is None
    assert page.max_tokens is None
    assert not assess_page(page).truncated


def test_assess_page_reads_model_signals_off_the_page_text():
    page = PageText(DENSE_PAGE_COMPLETE, finish_reason="length",
                    completion_tokens=4096, max_tokens=4096)
    integrity = assess_page(page, page_index=1)
    # structurally clean, but the endpoint said it ran out of tokens -> flagged
    assert integrity.truncated
    assert integrity.finish_reason == "length"
    assert integrity.signals == [SIGNAL_FINISH_REASON, SIGNAL_TOKEN_CEILING]


def test_plain_strings_are_assessable_without_model_signals():
    integrity = assess_page(DENSE_PAGE_TRUNCATED)
    assert integrity.truncated and integrity.finish_reason is None


def test_page_integrity_serializes_to_a_plain_dict():
    payload = assess_page(PageText(DENSE_PAGE_TRUNCATED, finish_reason="length"),
                          page_index=4).to_dict()
    assert payload["page_index"] == 4
    assert payload["truncated"] is True
    assert payload["finish_reason"] == "length"
    assert isinstance(payload["signals"], list) and payload["signals"]


# ---------------------------------------------------------------------------
# OCR client: the endpoint's own signals reach the page text
# ---------------------------------------------------------------------------

class _M:  # generic attribute holder, matching tests/test_ocr_client.py
    pass


class _FakeCompletions:
    def __init__(self, text, finish_reason=None, completion_tokens=None):
        self.text = text
        self.finish_reason = finish_reason
        self.completion_tokens = completion_tokens
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            return self._stream()
        choice = _M()
        choice.message = _M()
        choice.message.content = self.text
        if self.finish_reason is not None:
            choice.finish_reason = self.finish_reason
        resp = _M()
        resp.choices = [choice]
        if self.completion_tokens is not None:
            resp.usage = _M()
            resp.usage.completion_tokens = self.completion_tokens
        return resp

    def _stream(self):
        mid = len(self.text) // 2
        for part in (self.text[:mid], self.text[mid:]):
            chunk = _M()
            choice = _M()
            choice.delta = _M()
            choice.delta.content = part
            chunk.choices = [choice]
            yield chunk
        # Terminal chunk: empty delta, finish_reason attached (the real shape).
        chunk = _M()
        choice = _M()
        choice.delta = _M()
        choice.delta.content = None
        choice.finish_reason = self.finish_reason
        chunk.choices = [choice]
        yield chunk
        if self.completion_tokens is not None:
            # A usage-only trailing chunk carries no choices at all.
            usage_chunk = _M()
            usage_chunk.choices = []
            usage_chunk.usage = _M()
            usage_chunk.usage.completion_tokens = self.completion_tokens
            yield usage_chunk


class _FakeClient:
    def __init__(self, text, finish_reason=None, completion_tokens=None):
        self.chat = _M()
        self.chat.completions = _FakeCompletions(text, finish_reason, completion_tokens)


def _settings():
    return Settings(base_url="http://x/v1", api_key="k", model="m", timeout=1, retries=1,
                    max_workers=1, ngram_size=35, window_size=128)


def _img():
    return Image.new("RGB", (40, 40), (255, 255, 255))


def test_ocr_page_carries_the_endpoint_finish_reason_and_usage():
    client = _FakeClient("<table><tr><td>03/19</td><td>DEPO",
                         finish_reason="length", completion_tokens=4096)
    out = ocr_page(_img(), settings=_settings(), client=client)
    assert out.finish_reason == "length"
    assert out.completion_tokens == 4096
    assert out.max_tokens == 4096  # ocr_client._MAX_TOKENS, the ceiling requested
    assert assess_page(out).truncated


def test_ocr_page_carries_the_finish_reason_from_the_final_stream_chunk():
    client = _FakeClient("HELLO WORLD 12345", finish_reason="length", completion_tokens=4096)
    deltas = []
    out = ocr_page(_img(), settings=_settings(), client=client, on_delta=deltas.append)
    assert "".join(deltas) == "HELLO WORLD 12345"  # streaming unchanged
    assert out == "HELLO WORLD 12345"
    assert out.finish_reason == "length"
    assert out.completion_tokens == 4096


def test_ocr_page_reports_no_model_signal_when_the_endpoint_is_silent():
    # The bundled local_ocr_server.py reports finish_reason but never usage;
    # a barer endpoint reports neither. Neither case may invent a flag.
    client = _FakeClient("# Page markdown\n<table></table>")
    out = ocr_page(_img(), settings=_settings(), client=client)
    assert out == "# Page markdown\n<table></table>"
    assert out.finish_reason is None and out.completion_tokens is None
    assert not assess_page(out).truncated

    stopped = _FakeClient("# Page markdown\n<table></table>", finish_reason="stop")
    assert not assess_page(ocr_page(_img(), settings=_settings(), client=stopped)).truncated


# ---------------------------------------------------------------------------
# The intake ladder surfaces the flag on StatementMarkdown
# ---------------------------------------------------------------------------

def test_ladder_flags_a_truncated_visual_page_and_leaves_clean_pages_alone(monkeypatch):
    pages = [DENSE_PAGE_COMPLETE, DENSE_PAGE_TRUNCATED, DENSE_PAGE_COMPLETE]
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=300: pages)

    doc = parse_statement(b"%PDF", force_ocr=True, max_workers=1,
                          page_ocr_fn=lambda image: image)
    assert doc.truncated_pages == [1]
    assert doc.has_truncated_pages
    assert doc.page_integrity[1].signals == [SIGNAL_OPEN_TABLE, SIGNAL_OPEN_ROW,
                                             SIGNAL_OPEN_CELL]
    assert [item.truncated for item in doc.page_integrity] == [False, True, False]


def test_ladder_flags_a_model_reported_truncation_on_a_structurally_clean_page(monkeypatch):
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=300: ["img0"])
    monkeypatch.setattr(
        "ocr.ocr_client.ocr_page",
        lambda image, *, settings, client, on_delta=None: PageText(
            DENSE_PAGE_COMPLETE, finish_reason="length", completion_tokens=4096,
            max_tokens=4096),
    )
    monkeypatch.setattr("ocr.ocr_client._build_client", lambda settings: object())

    doc = parse_statement(b"%PDF", force_ocr=True, max_workers=1)
    assert doc.truncated_pages == [0]
    assert doc.page_integrity[0].finish_reason == "length"


def test_flag_is_advisory_only_and_changes_no_extraction_output(monkeypatch):
    pages = [DENSE_PAGE_COMPLETE, DENSE_PAGE_TRUNCATED]
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=300: pages)

    doc = parse_statement(b"%PDF", source_file="s.pdf", force_ocr=True, max_workers=1,
                          page_ocr_fn=lambda image: image)
    assert doc.has_truncated_pages
    # The pages, and the markdown every parser consumes, are byte-identical to
    # what the same read produced before O-3 existed.
    assert list(doc.pages) == pages
    assert all(type(page) is str for page in doc.pages)
    assert doc.to_markdown() == StatementMarkdown(
        source_file="s.pdf", model=doc.model, pages=pages).to_markdown()


def test_flags_describe_the_read_that_was_kept_not_a_discarded_one(monkeypatch):
    # TD page-1 recovery: the first read is truncated, a render variant recovers
    # the full page. The kept read is clean, so nothing may be flagged.
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=300: ["main"])
    monkeypatch.setattr("ocr.rasterize.rasterize_page", lambda b, i, dpi=200: "rec")
    monkeypatch.setattr("ocr.ocr_client._mask_qr", lambda image: image)
    monkeypatch.setattr("ocr.ocr_client._build_client", lambda settings: object())

    truncated = PageText("TD Bank STATEMENT OF ACCOUNT\n" + DENSE_PAGE_TRUNCATED,
                         finish_reason="length", max_tokens=4096, completion_tokens=4096)
    full = PageText("TD Bank STATEMENT OF ACCOUNT\nACCOUNT SUMMARY\n" + DENSE_PAGE_COMPLETE,
                    finish_reason="stop")
    monkeypatch.setattr(
        "ocr.ocr_client.ocr_page",
        lambda image, *, settings, client, on_delta=None: truncated if image == "main" else full,
    )

    doc = parse_statement(b"%PDF", force_ocr=True, max_workers=1)
    assert doc.pages == [str(full)]
    assert doc.truncated_pages == []  # the discarded truncated read is not reported


def test_flags_report_a_recovery_that_did_not_recover(monkeypatch):
    # Same path, but every render variant still truncates: the kept read is the
    # original truncated one, and it must be flagged.
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=300: ["main"])
    monkeypatch.setattr("ocr.rasterize.rasterize_page", lambda b, i, dpi=200: "rec")
    monkeypatch.setattr("ocr.ocr_client._mask_qr", lambda image: image)
    monkeypatch.setattr("ocr.ocr_client._build_client", lambda settings: object())

    truncated = PageText("TD Bank STATEMENT OF ACCOUNT\n" + DENSE_PAGE_TRUNCATED,
                         finish_reason="length", max_tokens=4096, completion_tokens=4096)
    monkeypatch.setattr("ocr.ocr_client.ocr_page",
                        lambda image, *, settings, client, on_delta=None: truncated)

    doc = parse_statement(b"%PDF", force_ocr=True, max_workers=1)
    assert doc.truncated_pages == [0]
    assert doc.page_integrity[0].signals[0] == SIGNAL_FINISH_REASON


def test_offline_rungs_are_assessed_too(monkeypatch):
    native = StatementMarkdown(
        source_file="s.pdf", model="native-pdf-text",
        pages=["NAVY FEDERAL\nBeginning Balance 11,982.22", "Page 2 of 2"],
    )
    monkeypatch.setattr("ocr.pipeline._native_statement",
                        lambda pdf_bytes, source_file="": native)
    doc = parse_statement(b"%PDF-fake", allow_visual_ocr=False)
    # assessed (so "empty" can never be confused with "exempt") and clean
    assert len(doc.page_integrity) == 2
    assert doc.truncated_pages == [] and not doc.has_truncated_pages


def test_statement_markdown_built_outside_the_ladder_reports_nothing():
    doc = StatementMarkdown(source_file="x.pdf", model="m", pages=["# A"])
    assert doc.page_integrity == []
    assert doc.truncated_pages == [] and not doc.has_truncated_pages


# ---------------------------------------------------------------------------
# Corpus parity — no validated document may be flagged
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUDIT_CSV = PROJECT_ROOT / "docs" / "balance-metrics-audit-results.csv"
CORPUS = PROJECT_ROOT / "Bank Statements"


def _audit_rows():
    if not CORPUS.is_dir() or not AUDIT_CSV.exists():
        pytest.skip("statement corpus or audit CSV not present")
    with open(AUDIT_CSV, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 109
    return rows


def _artifact_pages(markdown: str) -> list[str]:
    """Split a committed OCR artifact back into its per-page sections."""
    return re.split(r"^--- Page \d+.*---$", markdown, flags=re.MULTILINE)


def test_no_committed_corpus_ocr_artifact_page_is_flagged():
    """The 6 image-only corpus statements are served from committed OCR
    artifacts — the only OCR-produced text the gate audits. None may flag."""
    entries = manifest_entries()
    assert len(entries) == 6
    flagged = []
    for entry in entries.values():
        markdown = (DEFAULT_CACHE / entry["artifact"]).read_text(encoding="utf-8")
        pages = _artifact_pages(markdown)
        assert len(pages) > 1  # the split really found page sections
        for index, page in enumerate(pages):
            integrity = assess_page(page, page_index=index)
            if integrity.truncated:
                flagged.append(f"{entry['statement']} page {index}: {integrity.signals}")
    assert not flagged, "\n".join(flagged)


def test_no_corpus_native_page_is_flagged():
    """Every page of native text the ladder can emit for the 109 pinned
    documents, assessed. Uses the shared page builder (ocr/native_text.py::
    _native_pages) that every native extractor composes its output from, so the
    default suite gets a corpus-wide precision proof in ~3 s; the full-ladder
    version below is the corpus-marked twin."""
    flagged = []
    for row in _audit_rows():
        pdf_bytes = (CORPUS / row["path"]).read_bytes()
        for index, page in enumerate(_native_pages(pdf_bytes)):
            integrity = assess_page(page, page_index=index)
            if integrity.truncated:
                flagged.append(f"{row['path']} page {index}: {integrity.signals}")
    assert not flagged, "\n".join(flagged)


@pytest.mark.corpus
def test_no_corpus_document_is_flagged_through_the_real_ladder():
    """The production path itself: parse_statement over all 109 pinned PDFs
    (offline rungs only — the corpus never reaches visual OCR), asserting the
    ladder attaches an assessment to every page and flags none of them."""
    flagged = []
    for row in _audit_rows():
        pdf_bytes = (CORPUS / row["path"]).read_bytes()
        doc = parse_statement(pdf_bytes, source_file=row["path"], allow_visual_ocr=False)
        if doc is None:
            continue  # image-only: served from the committed artifact above
        assert len(doc.page_integrity) == len(doc.pages), row["path"]
        if doc.has_truncated_pages:
            flagged.append(f"{row['path']}: pages {doc.truncated_pages}")
    assert not flagged, "\n".join(flagged)

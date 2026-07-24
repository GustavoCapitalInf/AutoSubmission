from PIL import Image
from ocr.config import Settings
from ocr.ocr_client import (
    build_prompt, image_to_data_uri, ocr_page, strip_det_tags, strip_refusal_commentary,
    split_fused_header_row, fix_amount_column_bleed, collapse_repeated_amounts,
    collapse_repeated_page_numbers, embed_image_regions, strip_placeholder_markers,
    postprocess, looks_missegmented, repair_fused_amount_table,
    is_td_statement, looks_truncated_td,
)


def test_looks_truncated_td_detects_header_only_page():
    truncated = ("TD Bank America's Most Convenient Bank STATEMENT OF ACCOUNT\n"
                 "NARROWCAST MEDIA LLC\nPage: 1 of 10\nCust Ref #: 826-713")
    assert is_td_statement(truncated)
    assert looks_truncated_td(truncated)


def test_looks_truncated_td_false_when_body_present():
    full = ("TD Bank STATEMENT OF ACCOUNT\nACCOUNT SUMMARY\nBeginning Balance 11,982.22")
    assert not looks_truncated_td(full)


def test_looks_truncated_td_false_for_non_td():
    # Another bank's page with 'statement of account' must not trigger TD logic.
    assert not looks_truncated_td("Chase STATEMENT OF ACCOUNT\nsome header only")


_ORPHAN = ("<table><tr><td>AMOUNT($)</td></tr><tr><td>66.07</td></tr>"
           "<tr><td>1.00</td></tr><tr><td>2,100.00</td></tr></table>")
_CLEAN_TABLE = ("<table><tr><td>DATE</td><td>DESCRIPTION</td><td>AMOUNT($)</td></tr>"
                "<tr><td>03/19</td><td>DEBIT CARD FOOD LION</td><td>66.07</td></tr></table>")


def test_looks_missegmented_detects_orphan_amount_table():
    assert looks_missegmented("Other withdrawals\n" + _ORPHAN)


def test_looks_missegmented_ignores_normal_tables():
    assert not looks_missegmented(_CLEAN_TABLE)
    # a legit single amount cell (not a run) must not trip it
    assert not looks_missegmented("<table><tr><td>AMOUNT($)</td></tr><tr><td>5.00</td></tr></table>")


def test_repair_fused_amount_table_partial_fusion_and_spill():
    # Chase-style: header fused into row 1, description spilled into a 4th column,
    # and later rows alternate 3-cell / 4-cell.
    fused = (
        "<table>"
        "<tr><td>DATE04/06</td><td>DESCRIPTIONOrig CO Name:Sq</td>"
        "<td>Orig ID:9424 Ind Name:Choudhri</td><td>AMOUNT260.00</td></tr>"
        "<tr><td>04/06</td><td>Payment Received</td><td>04/05 Lyft Card 0298</td><td>235.17</td></tr>"
        "<tr><td>04/13</td><td>Zelle From Mumtaz</td><td>450.00</td></tr>"
        "</table>"
    )
    out = repair_fused_amount_table(fused)
    assert "<td>DATE</td><td>DESCRIPTION</td><td>AMOUNT</td>" in out  # clean header
    assert "DATE04/06" not in out and "AMOUNT260.00" not in out       # fusion gone
    # first data row reconstructed from the fused header row, description merged
    assert "<td>04/06</td><td>Orig CO Name:Sq Orig ID:9424 Ind Name:Choudhri</td><td>260.00</td></tr>" in out
    # 4-cell row collapsed to 3, description merged, amount preserved
    assert "<td>04/06</td><td>Payment Received 04/05 Lyft Card 0298</td><td>235.17</td></tr>" in out
    # 3-cell row unchanged
    assert "<td>04/13</td><td>Zelle From Mumtaz</td><td>450.00</td></tr>" in out


def test_repair_fused_amount_table_leaves_normal_tables():
    # A correct table (and a legit "AMOUNT($)" header) must be untouched.
    clean = ("<table><tr><td>DATE</td><td>CHECK #</td><td>AMOUNT($)</td></tr>"
             "<tr><td>03/23</td><td>207</td><td>74.08</td></tr></table>")
    assert repair_fused_amount_table(clean) == clean
    # a debit/credit/balance table must never be collapsed to 3 columns
    dcb = ("<table><tr><td>DATE04/06</td><td>DESCRIPTIONx</td><td>DEBIT10.00</td>"
           "<td>BALANCE5.00</td></tr></table>")
    assert repair_fused_amount_table(dcb) == dcb


def _img():
    return Image.new("RGB", (12, 8), (255, 255, 255))


def test_strip_placeholder_markers_drops_marker_lines():
    text = "Beginning Balance $100.00\n[Non-Text]\n[No text]\n[NO TEXT]\nEnding Balance $50.00"
    out = strip_placeholder_markers(text)
    assert "Non-Text" not in out and "No text" not in out and "NO TEXT" not in out
    assert "Beginning Balance $100.00" in out
    assert "Ending Balance $50.00" in out
    # marker-only lines are dropped, not left blank
    assert out == "Beginning Balance $100.00\nEnding Balance $50.00"


def test_strip_placeholder_markers_removes_inline_but_keeps_text():
    assert strip_placeholder_markers("Logo [Non-Text] here").strip() == "Logo  here".strip()


def test_strip_placeholder_markers_preserves_bracketed_content():
    # Only text/non-text placeholders go; real bracketed content stays.
    text = "[Continued] see page 2\nCheck [image] attached"
    assert strip_placeholder_markers(text) == text


def test_postprocess_strips_placeholder_markers():
    assert "Non-Text" not in postprocess("Deposits\n[Non-Text]\n$5.00")


def _settings():
    return Settings(base_url="http://x/v1", model="m", api_key="EMPTY", timeout=5,
                    retries=3, ngram_size=35, window_size=128, max_workers=3)


def test_image_to_data_uri():
    uri = image_to_data_uri(_img())
    assert uri.startswith("data:image/png;base64,")
    assert len(uri) > len("data:image/png;base64,")


def test_build_prompt_starts_with_image_token():
    p = build_prompt()
    assert p.startswith("<image>")
    assert len(p) > len("<image>")


def test_strip_det_tags_removes_region_annotations():
    raw = "<|det|>title [20, 82, 283, 147]<|/det|>HELLO WORLD"
    assert strip_det_tags(raw) == "HELLO WORLD"


def test_strip_det_tags_handles_multiple_tags():
    raw = ("<|det|>header [1, 2, 3, 4]<|/det|>CHASE\n"
           "<|det|>text [5, 6, 7, 8]<|/det|>Account: 123")
    assert strip_det_tags(raw) == "CHASE\nAccount: 123"


def test_collapse_repeated_amounts_collapses_degenerate_run():
    # Real BofA footer degeneration: -$200.27 repeated (with one -$200.17 outlier).
    raw = ("Total withdrawals and other debits\n"
           "-$200.27 -$200.27 -$200.27 -$200.17 -$200.27\n-$200.27\n-$200.27")
    out = collapse_repeated_amounts(raw)
    assert out == "Total withdrawals and other debits\n-$200.27"


def test_collapse_repeated_amounts_leaves_distinct_amounts():
    # A run of distinct amounts (no value repeated 3+ times) must be untouched.
    text = "$100.00 $200.00 $300.00"
    assert collapse_repeated_amounts(text) == text


def test_collapse_repeated_amounts_leaves_table_cells_untouched():
    # Amounts in table cells are separated by </td><td>, not bare whitespace.
    tbl = "<td>-$200.27</td><td>-$200.27</td><td>-$200.27</td><td>-$200.27</td>"
    assert collapse_repeated_amounts(tbl) == tbl


def test_embed_image_regions_crops_and_embeds():
    img = Image.new("RGB", (1000, 1000), (255, 0, 0))
    raw = ("<|det|>image [100, 100, 400, 400]<|/det|>"
           "<|det|>text [0, 0, 10, 10]<|/det|>hello")
    out = embed_image_regions(raw, img)
    # picture region -> embedded <img> crop
    assert '<img class="doc-image" src="data:image/png;base64,' in out
    assert "image [100" not in out
    # text region left intact for the normal det-stripping step
    assert "<|det|>text [0, 0, 10, 10]<|/det|>hello" in out


def test_embed_image_regions_ignores_text_only():
    img = Image.new("RGB", (100, 100), (0, 0, 0))
    raw = "<|det|>header [1, 2, 3, 4]<|/det|>CHASE"
    assert embed_image_regions(raw, img) == raw


def test_ocr_page_embeds_check_images(monkeypatch):
    # A page that returns an image region should render an <img> crop.
    img = Image.new("RGB", (1000, 1000), (0, 128, 255))
    client = _FakeClient("<|det|>image [200, 200, 800, 800]<|/det|>")
    out = ocr_page(img, settings=_settings(), client=client)
    assert '<img class="doc-image" src="data:image/png;base64,' in out


def test_collapse_repeated_page_numbers():
    assert collapse_repeated_page_numbers("Page 4 of 10 Page 4 of 10") == "Page 4 of 10"
    assert collapse_repeated_page_numbers(
        "Page 4 of 10 Page 4 of 10 Page 4 of 10") == "Page 4 of 10"
    # Distinct pages must NOT collapse.
    assert collapse_repeated_page_numbers(
        "Page 4 of 10 Page 5 of 10") == "Page 4 of 10 Page 5 of 10"


def test_strip_det_tags_removes_orphan_footer_tags():
    # Unclosed tags the model emits around footers (no <|/det|>).
    raw = ("Total withdrawals and other debits -$200.27 "
           "<|det|>footer [819, 811, 942, 825] -$200.27 "
           "<|det|>footer [819, 811, 942, 825]] Page 4 of 10")
    out = strip_det_tags(raw)
    assert "<|det|>" not in out
    assert "footer" not in out
    assert "-$200.27" in out
    assert "Page 4 of 10" in out


def test_strip_refusal_commentary_removes_inline_refusal():
    raw = (
        "STATEMENT OF ACCOUNT\n"
        "The image provided is a QR code. It does not contain any text, "
        "mathematical formulas, tables, or figures that can be processed "
        "according to the OCR instructions. Therefore, no textual content "
        "can be extracted from this image.\n"
        "Go paperless."
    )
    out = strip_refusal_commentary(raw)
    assert "QR code" not in out
    assert "cannot be processed" not in out
    assert "STATEMENT OF ACCOUNT" in out
    assert "Go paperless." in out


def test_strip_refusal_commentary_leaves_normal_text_alone():
    text = "CHASE\nAccount: 123\nBeginning balance $100.00"
    assert strip_refusal_commentary(text) == text


def test_split_fused_header_row_splits_chase_deposits_table():
    # Real Unlimited-OCR output: the header row is fused into the first data row.
    raw = (
        "<table>"
        "<tr><td>DATE01/02</td><td>DESCRIPTIONOrig CO Name:Paymentech Trn: 0024333937Tc</td>"
        "<td>AMOUNT$1,000.00</td></tr>"
        "<tr><td>01/06</td><td>Orig CO Name:Paymentech Trn: 0066135043Tc</td><td>4,870.00</td></tr>"
        "</table>"
    )
    out = split_fused_header_row(raw)
    # A proper header row is recovered...
    assert "<tr><td>DATE</td><td>DESCRIPTION</td><td>AMOUNT</td></tr>" in out
    # ...and the first data row is clean.
    assert "<td>01/02</td>" in out
    assert "<td>Orig CO Name:Paymentech Trn: 0024333937Tc</td>" in out
    assert "<td>$1,000.00</td>" in out
    # No fused cell remains.
    assert "DATE01/02" not in out
    assert "AMOUNT$1,000.00" not in out
    # The already-clean second row is untouched.
    assert "<tr><td>01/06</td><td>Orig CO Name:Paymentech Trn: 0066135043Tc</td><td>4,870.00</td></tr>" in out


def test_split_fused_header_row_leaves_clean_header_untouched():
    # BofA-style: header row is already correct — must not be altered.
    clean = (
        "<table><tr><td>Date</td><td>Description</td><td>Amount</td></tr>"
        "<tr><td>11/03/25</td><td>Online Banking transfer</td><td>6,000.00</td></tr></table>"
    )
    assert split_fused_header_row(clean) == clean


def test_split_fused_header_row_leaves_label_value_summary_untouched():
    # Chase balance summary: first cell is not a header+value fusion, and
    # "ACCOUNT 000000..." has a space (legit label), so nothing must split.
    summary = (
        "<table><tr><td>Checking &amp; Savings</td><td>ACCOUNT</td>"
        "<td>BEGINNING BALANCE THIS PERIOD</td></tr>"
        "<tr><td>Chase Platinum</td><td>000000727011905</td><td>$28,314.72</td></tr></table>"
    )
    assert split_fused_header_row(summary) == summary


def test_fix_amount_column_bleed_moves_wrapped_desc_out_of_amount():
    # Real BofA output: wrapped description continuation bled into the Amount column.
    raw = (
        "<table><tr><td>Date</td><td>Description</td><td>Amount</td></tr>"
        "<tr><td>11/03/25</td><td>ONLINE PAYROLL DES:PAYROLL ID:0000217279 CCD</td>"
        "<td>ID:9531796 INDN:HEARTLAND FINANCIAL SE CO -74.88</td></tr>"
        "<tr><td>11/05/25</td><td>THE HARTFORD DES:INSPMTCL CCD</td><td>-110.00</td></tr>"
        "</table>"
    )
    out = fix_amount_column_bleed(raw)
    # Broken row: amount cell is now just the money...
    assert "<td>-74.88</td>" in out
    assert "HEARTLAND FINANCIAL SE CO -74.88" not in out
    # ...and the bled text was appended to that row's description.
    assert ("<td>ONLINE PAYROLL DES:PAYROLL ID:0000217279 CCD "
            "ID:9531796 INDN:HEARTLAND FINANCIAL SE CO</td>") in out
    # Clean row (money only) is untouched.
    assert "<tr><td>11/05/25</td><td>THE HARTFORD DES:INSPMTCL CCD</td><td>-110.00</td></tr>" in out


def test_fix_amount_column_bleed_ignores_tables_without_amount_header():
    other = (
        "<table><tr><td>Item</td><td>Note</td></tr>"
        "<tr><td>Foo</td><td>bar baz -74.88</td></tr></table>"
    )
    assert fix_amount_column_bleed(other) == other


def test_fix_amount_column_bleed_leaves_clean_amount_table_untouched():
    clean = (
        "<table><tr><td>Date</td><td>Description</td><td>Amount</td></tr>"
        "<tr><td>11/03/25</td><td>Online Banking transfer Confirmation# 7701269064</td>"
        "<td>6,000.00</td></tr></table>"
    )
    assert fix_amount_column_bleed(clean) == clean


class _M:  # generic attribute holder
    pass


class _FakeCompletions:
    def __init__(self, text, fail_times=0):
        self.text = text
        self.fail_times = fail_times
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("transient")
        if kwargs.get("stream"):
            return self._stream()
        m = _M()
        m.message = _M()
        m.message.content = self.text
        r = _M()
        r.choices = [m]
        return r

    def _stream(self):
        # Yield the text in a couple of chunks as streaming deltas.
        mid = len(self.text) // 2
        for part in (self.text[:mid], self.text[mid:]):
            chunk = _M()
            choice = _M()
            choice.delta = _M()
            choice.delta.content = part
            chunk.choices = [choice]
            yield chunk


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


class _FakeClient:
    def __init__(self, text, fail_times=0):
        self.chat = _FakeChat(_FakeCompletions(text, fail_times))


def test_ocr_page_sends_image_and_prompt_with_required_params():
    client = _FakeClient("# Page markdown\n<table></table>")
    out = ocr_page(_img(), settings=_settings(), client=client)
    assert out == "# Page markdown\n<table></table>"
    sent = client.chat.completions.calls[0]
    assert sent["model"] == "m"
    # text content comes before the image, and starts with the <image> token
    content = sent["messages"][-1]["content"]
    assert content[0]["type"] == "text"
    assert content[0]["text"].startswith("<image>")
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    # required extra params for this model
    assert sent["extra_body"]["skip_special_tokens"] is False
    assert sent["extra_body"]["vllm_xargs"] == {"ngram_size": 35, "window_size": 128}


def test_ocr_page_strips_det_tags_from_response():
    client = _FakeClient("<|det|>title [1, 2, 3, 4]<|/det|>HELLO WORLD 12345")
    out = ocr_page(_img(), settings=_settings(), client=client)
    assert out == "HELLO WORLD 12345"


def test_ocr_page_retries_then_succeeds():
    client = _FakeClient("ok", fail_times=2)
    out = ocr_page(_img(), settings=_settings(), client=client)
    assert out == "ok"
    assert len(client.chat.completions.calls) == 3


def test_ocr_page_streams_deltas_to_callback():
    client = _FakeClient("HELLO WORLD 12345")
    deltas = []
    out = ocr_page(_img(), settings=_settings(), client=client,
                   on_delta=lambda d: deltas.append(d))
    # streaming was requested...
    assert client.chat.completions.calls[0].get("stream") is True
    # ...chunks were delivered live...
    assert "".join(deltas) == "HELLO WORLD 12345"
    assert len(deltas) >= 2
    # ...and the returned value is still the (cleaned) full text.
    assert out == "HELLO WORLD 12345"

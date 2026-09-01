"""ocr_client: intake-detection helpers, embed_image_regions, and the analysis
path's quarantine of the nine-function `postprocess` chain (OQ1 = C).

The per-function behavior of the nine `postprocess` members
(strip_det_tags, strip_refusal_commentary, strip_placeholder_markers,
strip_oversized_embedded_images, collapse_repeated_amounts,
collapse_repeated_page_numbers, split_fused_header_row,
repair_fused_amount_table, fix_amount_column_bleed) is pinned by the
executable census (`tests/test_ocr_postprocess_census.py` +
`tests/fixtures/ocr_postprocess/`), not here — see
`docs/moneythumb-replacement/OCR_POSTPROCESS_CENSUS.md`. What lives here is:
the intake-detection helpers those functions don't cover (TD / mis-segmentation
detection), `embed_image_regions` (unwired from the analysis path but kept
importable), and the quarantine wiring itself: `ocr_page` must return the
model's raw completion string, `postprocess` must remain callable directly but
never be invoked by `ocr_page`, and `apply_admitted` must apply exactly the
members named in `ADMITTED_POSTPROCESS` (empty in Phase 2.0) in order.
"""
from PIL import Image
from ocr.config import Settings
from ocr.ocr_client import (
    ADMITTED_POSTPROCESS, POSTPROCESS_STATE, INTAKE_FURNITURE,
    build_prompt, image_to_data_uri, ocr_page, apply_admitted, postprocess,
    embed_image_regions, looks_missegmented, is_td_statement, looks_truncated_td,
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


def _img():
    return Image.new("RGB", (12, 8), (255, 255, 255))


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


def test_embed_image_regions_crops_and_embeds():
    # embed_image_regions itself is unchanged and stays importable for a
    # future display-only use (see INTAKE_FURNITURE / OCR_POSTPROCESS_CENSUS);
    # it is simply never called from ocr_page any more (below).
    img = Image.new("RGB", (1000, 1000), (255, 0, 0))
    raw = ("<|det|>image [100, 100, 400, 400]<|/det|>"
           "<|det|>text [0, 0, 10, 10]<|/det|>hello")
    out = embed_image_regions(raw, img)
    assert '<img class="doc-image" src="data:image/png;base64,' in out
    assert "image [100" not in out
    assert "<|det|>text [0, 0, 10, 10]<|/det|>hello" in out


def test_embed_image_regions_drops_oversized_regions():
    img = Image.new("RGB", (1000, 1000), (255, 0, 0))
    raw = "<|det|>image [0, 0, 1000, 900]<|/det|>legal notice text"
    out = embed_image_regions(raw, img)
    assert "data:image/png;base64" not in out
    assert out == "legal notice text"


def test_embed_image_regions_drops_tall_disclosure_slices():
    img = Image.new("RGB", (2500, 3300), (255, 0, 0))
    raw = "<|det|>image [350, 250, 600, 800]<|/det|>legal notice text"
    out = embed_image_regions(raw, img)
    assert "data:image/png;base64" not in out
    assert out == "legal notice text"


def test_embed_image_regions_ignores_text_only():
    img = Image.new("RGB", (100, 100), (0, 0, 0))
    raw = "<|det|>header [1, 2, 3, 4]<|/det|>CHASE"
    assert embed_image_regions(raw, img) == raw


# ---------------------------------------------------------------------------
# OQ1 = C — the quarantine itself. `postprocess` stays importable and correct
# as a pure function (its own executable census proves what each member does);
# what these tests pin is that NOTHING on the analysis path calls it any more.
# ---------------------------------------------------------------------------

def test_postprocess_state_is_quarantined():
    assert POSTPROCESS_STATE == "quarantined"


def test_admitted_postprocess_is_empty_in_phase_2_0():
    # Mutation table: `ADMITTED_POSTPROCESS = ("strip_det_tags",)` must fail
    # this exact assertion. Nothing is re-admitted in Phase 2.0.
    assert ADMITTED_POSTPROCESS == ()
    assert isinstance(ADMITTED_POSTPROCESS, tuple)


def test_apply_admitted_is_a_noop_with_the_default_empty_tuple():
    degenerate = "$50.00 $50.00 $50.00 $75.00 $60.00"
    assert apply_admitted(degenerate) == degenerate
    tagged = "<|det|>title [1, 2, 3, 4]<|/det|>HELLO"
    assert apply_admitted(tagged) == tagged


def test_apply_admitted_applies_named_members_in_the_given_order(monkeypatch):
    # Mutation table: "apply_admitted applies a non-admitted member" — proves
    # apply_admitted is driven by the ADMITTED_POSTPROCESS tuple's own order,
    # not by postprocess()'s hardcoded chain order.
    import ocr.ocr_client as ocr_client_module
    monkeypatch.setattr(ocr_client_module, "ADMITTED_POSTPROCESS",
                        ("strip_det_tags", "collapse_repeated_amounts"))
    raw = "<|det|>x [1,2,3,4]<|/det|>$50.00 $50.00 $50.00 $75.00 $60.00"
    out = apply_admitted(raw)
    assert "<|det|>" not in out          # strip_det_tags ran
    assert out == "$50.00"               # collapse_repeated_amounts then ran


def test_apply_admitted_never_applies_an_unlisted_member(monkeypatch):
    import ocr.ocr_client as ocr_client_module
    monkeypatch.setattr(ocr_client_module, "ADMITTED_POSTPROCESS", ("strip_det_tags",))
    raw = "<|det|>x [1,2,3,4]<|/det|>$50.00 $50.00 $50.00 $75.00 $60.00"
    out = apply_admitted(raw)
    assert "<|det|>" not in out          # the one admitted member ran
    assert out == "$50.00 $50.00 $50.00 $75.00 $60.00"  # collapse NOT applied


def test_postprocess_remains_importable_and_correct_as_a_pure_function():
    # Kept for re-admission evidence, never called from ocr_page or render.py.
    assert "Non-Text" not in postprocess("Deposits\n[Non-Text]\n$5.00")


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


def test_ocr_page_returns_raw_det_tags_unremoved():
    # Mutation table: "ocr_page calls postprocess again" — killed by this
    # exact assertion (postprocess would strip the det tag).
    raw = "<|det|>title [1, 2, 3, 4]<|/det|>HELLO WORLD 12345"
    client = _FakeClient(raw)
    out = ocr_page(_img(), settings=_settings(), client=client)
    assert out == raw


def test_ocr_page_does_not_collapse_repeated_amounts():
    # F-1 (collapse_repeated_amounts) must never run on the analysis path.
    raw = "Total withdrawals\n-$200.27 -$200.27 -$200.27 -$200.17 -$200.27"
    client = _FakeClient(raw)
    out = ocr_page(_img(), settings=_settings(), client=client)
    assert out == raw
    assert out.count("-$200.27") == 4  # nothing collapsed or deleted
    assert "-$200.17" in out           # the distinct amount survives


def test_ocr_page_does_not_fix_amount_column_bleed():
    # F-11 (fix_amount_column_bleed) must never run on the analysis path.
    raw = ("<table><tr><td>Date</td><td>Description</td><td>Amount</td></tr>"
           "<tr><td>01/02</td><td>ACH DEBIT</td><td>1,000.00 234.56</td></tr></table>")
    client = _FakeClient(raw)
    out = ocr_page(_img(), settings=_settings(), client=client)
    assert out == raw
    assert "<td>1,000.00 234.56</td>" in out


def test_ocr_page_does_not_strip_refusal_placeholder_or_oversized_image():
    big_uri = "data:image/png;base64," + ("A" * 100)
    raw = (
        "The image provided is a QR code. It does not contain any text. "
        "Therefore, no textual content can be extracted from this image.\n"
        "[Non-Text]\n"
        f'<img class="doc-image" src="{big_uri}" alt="image" />'
    )
    client = _FakeClient(raw)
    out = ocr_page(_img(), settings=_settings(), client=client)
    assert out == raw


def test_ocr_page_does_not_embed_image_regions():
    # F-2: document pixels never enter the text the validator reads. Before
    # this quarantine, an image-region det tag was replaced by an embedded
    # <img> crop; now the raw det tag survives untouched.
    img = Image.new("RGB", (1000, 1000), (0, 128, 255))
    raw = "<|det|>image [250, 250, 700, 700]<|/det|>"
    client = _FakeClient(raw)
    out = ocr_page(img, settings=_settings(), client=client)
    assert out == raw
    assert "data:image/png;base64" not in out


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
    # ...and the returned value is still the raw full text (no cleanup ran).
    assert out == "HELLO WORLD 12345"


# ---------------------------------------------------------------------------
# OQ2 = YES — INTAKE_FURNITURE is the only sanctioned home for issuer-named
# intake behavior. Structural pins live in tests/test_ocr_intake_furniture.py;
# this is the minimal "the register names what this module actually has"
# check that belongs beside the functions themselves.
# ---------------------------------------------------------------------------

def test_intake_furniture_register_names_the_td_markers():
    assert "_TD_MARKERS_RE" in INTAKE_FURNITURE
    assert "_TD_RECOVERY_VARIANTS" in INTAKE_FURNITURE
    assert "_mask_qr" in INTAKE_FURNITURE
    for entry in INTAKE_FURNITURE.values():
        assert entry["scope"], "every INTAKE_FURNITURE entry must state its scope"
        assert entry["justification"], "every INTAKE_FURNITURE entry must be justified"

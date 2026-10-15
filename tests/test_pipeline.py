import inspect

import fitz
import pytest

from ocr.pipeline import FORCED_OCR_REMOVED, VISUAL_OCR_REMOVED, parse_statement

# Model-code removal, slice S2: the visual OCR rung's tests that used to open
# this file (the injected `page_ocr_fn`, page concurrency, the mis-segmentation
# re-OCR at `fallback_dpi`, the TD page-1 recovery, the `on_page_delta` live
# stream, the visual rung's place in the ladder) were deleted with the rung.
# Slice S5: the PaddleOCR rung's ladder tests (the forced Paddle branch, its
# data-scope contract, its inertness off the forced path, the drifted-evidence
# refusal) were deleted with that rung; forcing is now refused outright.


# ---------------------------------------------------------------------------
# O-1: the single intake ladder (native -> tesseract).
# Rungs are patched at their ONE home in ocr.pipeline; the extractors
# themselves are never touched.
# ---------------------------------------------------------------------------


class _NativeDoc:
    model = "native-pdf-text"
    pages = ["native page one", "native page two"]

    def to_markdown(self):
        return "# native"


class _TesseractDoc:
    model = "local-tesseract-ocr"
    pages = ["tesseract page"]

    def to_markdown(self):
        return "# tesseract"


def _forbid_reading(monkeypatch):
    """Any rung or preflight that runs fails the test: a refusal must come first."""
    for target in ("ocr.pipeline.inspect_pdf", "ocr.pipeline._native_statement",
                   "ocr.pipeline.parse_local_tesseract", "ocr.pipeline.native_evidence_from_pdf"):
        monkeypatch.setattr(target, lambda *a, **k: pytest.fail("nothing may be read before the refusal"))


def test_ladder_native_rung_wins_and_replays_pages(monkeypatch):
    monkeypatch.setattr("ocr.pipeline._native_statement",
                        lambda pdf_bytes, source_file="": _NativeDoc())
    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract",
                        lambda *a, **k: pytest.fail("tesseract rung must not run"))

    replayed = []
    stages = []
    doc = parse_statement(b"%PDF-fake", allow_local_ocr=True,
                          on_page_replace=lambda p, t: replayed.append((p, t)),
                          on_stage=stages.append)
    assert doc.model == "native-pdf-text"
    assert replayed == [(0, "native page one"), (1, "native page two")]
    assert stages == ["native"]
    # MAJOR-3: the native rung's per-page provenance, design item 3's first arm.
    assert doc.page_extractor == ["native-pdf-text", "native-pdf-text"]


def test_ladder_tesseract_rung_is_capability_gated(monkeypatch):
    tesseract_calls = []

    def fake_tesseract(pdf_bytes, source_file="", **kwargs):
        tesseract_calls.append(source_file)
        return _TesseractDoc()

    monkeypatch.setattr("ocr.pipeline._native_statement", lambda pdf_bytes, source_file="": None)
    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", fake_tesseract)

    # Without the capability the rung is skipped entirely (the CLI's posture)...
    assert parse_statement(b"%PDF-fake", allow_local_ocr=False, allow_visual_ocr=False) is None
    assert tesseract_calls == []
    # ...with it, the scan is served locally.
    doc = parse_statement(b"%PDF-fake", allow_local_ocr=True, allow_visual_ocr=False)
    assert doc.model == "local-tesseract-ocr"
    assert tesseract_calls == ["" ]
    # MAJOR-3: the Tesseract rung's per-page provenance, design item 3's second arm.
    assert doc.page_extractor == ["local-tesseract-ocr"]


def test_ladder_returns_none_when_the_offline_rungs_read_nothing(monkeypatch):
    monkeypatch.setattr("ocr.pipeline._native_statement", lambda pdf_bytes, source_file="": None)
    stages = []
    assert parse_statement(b"%PDF-fake", allow_visual_ocr=False, on_stage=stages.append) is None
    assert stages == ["native"]  # no further rung was announced
    # The default is the same call: allow_visual_ocr defaults to False now.
    stages.clear()
    assert parse_statement(b"%PDF-fake", on_stage=stages.append) is None
    assert stages == ["native"]


def test_ladder_profile_skips_native_for_textless_pdf(monkeypatch):
    # A REAL image-only PDF: the profile reports zero native text, so the
    # ladder never even calls the native extractors (safe: they all gate on
    # extracted text markers).
    blank = fitz.open()
    blank.new_page()
    pdf_bytes = blank.tobytes()

    monkeypatch.setattr("ocr.pipeline._native_statement",
                        lambda *a, **k: pytest.fail("native rung must be profile-skipped"))

    stages = []
    result = parse_statement(pdf_bytes, allow_visual_ocr=False, on_stage=stages.append)
    assert result is None
    assert stages == []  # no rung ran at all


def test_ladder_announces_every_rung_in_order(monkeypatch):
    monkeypatch.setattr("ocr.pipeline._native_statement", lambda pdf_bytes, source_file="": None)
    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", lambda *a, **k: None)

    stages = []
    assert parse_statement(b"%PDF-fake", allow_local_ocr=True, on_stage=stages.append) is None
    assert stages == ["native", "local_ocr"]


# ---------------------------------------------------------------------------
# Model-code removal, slice S2: the visual rung is refused, forcing needs
# Paddle, and every parameter after `source_file` is keyword-only.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("flags", [
    {"allow_visual_ocr": True},
    {"allow_visual_ocr": True, "allow_local_ocr": True},
    {"allow_visual_ocr": True, "force_ocr": True},
])
def test_asking_for_the_visual_rung_is_a_value_error_before_anything_is_read(monkeypatch, flags):
    _forbid_reading(monkeypatch)
    with pytest.raises(ValueError) as refused:
        parse_statement(b"%PDF-fake", **flags)
    assert str(refused.value) == VISUAL_OCR_REMOVED


@pytest.mark.parametrize("flags", [
    {"force_ocr": True},
    {"force_ocr": True, "allow_local_ocr": True},
    {"force_ocr": True, "allow_visual_ocr": False},
])
def test_forcing_is_a_value_error_before_anything_is_read(monkeypatch, flags):
    """Slice S5: forcing reached a model rung only (visual, then Paddle); both are gone, so `force_ocr=True` is
    refused with the fixed literal before any preflight or rung runs."""
    _forbid_reading(monkeypatch)
    with pytest.raises(ValueError) as refused:
        parse_statement(b"%PDF-fake", **flags)
    assert str(refused.value) == FORCED_OCR_REMOVED


@pytest.mark.parametrize("knob", [{"allow_paddle_ocr": True}, {"allow_paddle_ocr": False},
                                  {"paddle_data_scope": "synthetic"}, {"dpi": 300}])
def test_the_paddle_rungs_knobs_are_gone(monkeypatch, knob):
    """Slice S5: `allow_paddle_ocr`, `paddle_data_scope` and `dpi` (read only by the model rungs) left the ladder's
    signature; passing one is a TypeError, before anything is read."""
    _forbid_reading(monkeypatch)
    with pytest.raises(TypeError):
        parse_statement(b"%PDF-fake", **knob)


def test_every_parameter_after_source_file_is_keyword_only():
    parameters = inspect.signature(parse_statement).parameters
    assert list(parameters)[:2] == ["pdf_bytes", "source_file"]
    kinds = {name: parameter.kind for name, parameter in parameters.items()}
    assert kinds["pdf_bytes"] is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert kinds["source_file"] is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert all(kind is inspect.Parameter.KEYWORD_ONLY for name, kind in kinds.items()
               if name not in ("pdf_bytes", "source_file"))
    # The visual rung's own parameters are gone, and so are the Paddle rung's (slice S5).
    assert not set(parameters) & {"model", "page_ocr_fn", "on_page_delta", "max_workers", "fallback_dpi",
                                  "dpi", "allow_paddle_ocr", "paddle_data_scope"}
    assert parameters["force_ocr"].default is False
    assert parameters["allow_visual_ocr"].default is False
    with pytest.raises(TypeError):
        parse_statement(b"%PDF-fake", "s.pdf", 300)  # dpi used to be the third positional


def test_the_ladder_still_imports_rasterize_before_the_dotenv_loads():
    """Plan D20 / P16: `ocr.rasterize` reads POPPLER_PATH at import, and this
    module has always imported it before `ocr.document` -> `ocr.config` loads
    the .env. The visual rung that used its functions is gone; the order stays
    (an entry point that reaches the ladder first keeps the value it held)."""
    import ast

    import ocr.pipeline as pipeline_module

    tree = ast.parse(inspect.getsource(pipeline_module))
    order = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.level == 1:
            order.extend([node.module] if node.module else [alias.name for alias in node.names])
    assert "rasterize" in order and "document" in order, order
    assert order.index("rasterize") < order.index("document"), order


def test_a_page_extractor_length_mismatch_refuses_at_construction():
    """M7: `page_extractor` must have exactly one entry per page, or the
    construction refuses rather than silently mis-describing a page."""
    from ocr.document import StatementMarkdown

    with pytest.raises(Exception):
        StatementMarkdown(
            source_file="s.pdf", model="paddle-ocr+ppocrv5",
            pages=["a", "b"], page_extractor=["paddle-ocr+ppocrv5"],
        )

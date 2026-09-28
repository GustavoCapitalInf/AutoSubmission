"""Wave 2 / D-3 — content-hash artifact cache.

Two things are proven here and nothing else may substitute for them:

1. **Zero recomputation on identical bytes.** A call-counting fake stands in
   for the OCR ladder and for the analysis pipeline; re-processing the same
   PDF must leave both counters untouched. That is the hard requirement, so
   it is asserted at the worker level (the real ``run_job``), not against the
   cache primitives.
2. **Restart durability.** The store is torn down and reopened over the same
   data directory — exactly what a process restart constructs, the same
   simulation D-1 uses — and the hit must still occur.

Everything else here defends the cache KEY: each knob that changes a stage's
output must partition it, and nothing that leaves output unchanged may.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import unittest.mock
from dataclasses import dataclass
from pathlib import Path

import pytest

from evidence.canonical import ExtractionEvidence, PageEvidence, PageFrame, WordBox
from ocr.document import StatementMarkdown
from ocr.truncation import PageIntegrity
from webapp.artifact_cache import (
    ANALYSIS_STAGE_VERSION,
    EXTRACTION_SCHEMA_VERSION,
    OCR_STAGE_VERSION,
    ArtifactCache,
    CACHE_FINDING_EVIDENCE_DRIFT,
    CACHE_FORMAT_VERSION,
    STAGE_ANALYSIS,
    STAGE_OCR,
    STAGE_REPORT,
    analysis_input_sha,
    analysis_settings_key,
    cache_key,
    cached_analysis,
    cached_ocr,
    cached_report,
    content_sha256,
    ocr_settings_key,
    open_cache,
    report_settings_key,
    sheets_sha256,
    text_sha256,
)
from webapp.jobs import JobStore
from webapp.storage import Storage
from webapp.worker import run_job

ROOT = Path(__file__).resolve().parents[1]

PDF = b"%PDF-1.7\nartifact cache fixture body"
OTHER_PDF = b"%PDF-1.7\nartifact cache fixture body (different)"


@dataclass
class _OcrSettings:
    """Stand-in for ocr.config.Settings — only the keyed attributes matter.

    ``endpoint_class`` is not yet a real field of ``ocr.config.Settings``
    (cell B2 adds it); it is here because ``ocr_settings_key`` already reads
    it through ``getattr`` with a ``"loopback"`` default, and this fixture is
    "anything with the same attributes" per that function's own docstring."""

    model: str = "baidu/Unlimited-OCR"
    base_url: str = "http://localhost:8000/v1"
    ngram_size: int = 35
    window_size: int = 128
    max_workers: int = 1
    timeout: float = 120.0
    retries: int = 3
    api_key: str = "EMPTY"
    endpoint_class: str = "loopback"


@dataclass
class _AnalysisSettings:
    model: str = "gemini-3.5-flash-lite"
    escalation_model: str = "gemini-3.5-flash"
    withholding_denominator_mode: str = "legacy_eligible_deposits"
    api_key: str = ""


@pytest.fixture(autouse=True)
def _restore_toolchain_versions_cache():
    """Review MINOR-6: several tests below force
    `webapp.artifact_cache._toolchain_versions_cache` to a known value (or to
    `None`, to force a fresh probe) and used to reset it to `None` by hand on
    the happy path only — a failure between the force and the manual reset
    leaked the forced state into every later test in the session (and a
    forced `None` then triggers a REAL subprocess probe in whatever ran
    next). Autouse so no test can forget it."""
    import webapp.artifact_cache as module

    original = module._toolchain_versions_cache
    yield
    module._toolchain_versions_cache = original


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path / "data"


@pytest.fixture
def cache(data_dir):
    return ArtifactCache(Storage(data_dir))


def _reopen(data_dir) -> ArtifactCache:
    """A brand-new Storage + ArtifactCache over the same directory — what a
    process restart builds."""
    return ArtifactCache(Storage(data_dir))


def _doc(pages=("page one",), model="fake-ocr", source_file="s.pdf") -> StatementMarkdown:
    return StatementMarkdown(source_file=source_file, model=model, pages=list(pages))


def _doc_with_evidence(
    text: str = "hello world", model: str = "paddle-ocr+ppocrv5", source_file: str = "s.pdf",
) -> StatementMarkdown:
    """P21-ROUTING closure (MAJOR-1): a `StatementMarkdown` carrying real
    `page_extractor` / `evidence`, for the D6 round-trip tests. One word
    spanning the whole page text, so `evidence.page_texts() == [text]`
    exactly — the same trick `tests/test_pipeline.py::_fake_paddle_read` and
    `tests/test_paddle_routing.py::_claimable_paddle_read` use."""
    frame = PageFrame.pdf_points(page_index=0, width_pt=600.0, height_pt=800.0)
    word = WordBox(word_id="p0.l0.w0", page_index=0, text=text, x0=10.0, y0=10.0, x1=200.0, y1=25.0)
    page = PageEvidence(frame=frame, words=(word,))
    evidence = ExtractionEvidence(
        document_sha256="A" * 64, extractor_id="paddle-ocr", model_token=model,
        pages=(page,), runtime={"provider": "local", "execution_class": "local_free"},
    )
    return StatementMarkdown(
        source_file=source_file, model=model, pages=list(evidence.page_texts()),
        page_extractor=[model], evidence=evidence,
    )


# ---------------------------------------------------------------------------
# key composition
# ---------------------------------------------------------------------------


def test_content_hash_follows_the_established_uppercase_convention():
    import hashlib

    assert content_sha256(PDF) == hashlib.sha256(PDF).hexdigest().upper()
    assert text_sha256("abc") == hashlib.sha256(b"abc").hexdigest().upper()


def test_cache_key_joins_stage_input_and_settings():
    base = cache_key(STAGE_OCR, content_sha256(PDF), "SETTINGS")
    assert base == cache_key(STAGE_OCR, content_sha256(PDF), "SETTINGS")  # stable
    # Any one of the three components changing changes the key.
    assert base != cache_key(STAGE_ANALYSIS, content_sha256(PDF), "SETTINGS")
    assert base != cache_key(STAGE_OCR, content_sha256(OTHER_PDF), "SETTINGS")
    assert base != cache_key(STAGE_OCR, content_sha256(PDF), "OTHER")
    assert len(base) == 64 and base == base.upper()


@pytest.mark.parametrize(
    "changed",
    [
        {"force_ocr": True},
        {"allow_local_ocr": True},
        {"allow_visual_ocr": False},
        {"dpi": 200},
        {"fallback_dpi": None},
        {"ocr_settings": _OcrSettings(model="other/model")},
        {"ocr_settings": _OcrSettings(base_url="http://elsewhere/v1")},
        {"ocr_settings": _OcrSettings(ngram_size=40)},
        {"ocr_settings": _OcrSettings(window_size=256)},
        {"ocr_settings": _OcrSettings(endpoint_class="private")},
    ],
)
def test_every_ocr_knob_partitions_the_key(changed):
    baseline = dict(
        force_ocr=False,
        allow_local_ocr=False,
        allow_visual_ocr=True,
        dpi=300,
        fallback_dpi=250,
        ocr_settings=_OcrSettings(),
    )
    assert ocr_settings_key(**baseline) != ocr_settings_key(**{**baseline, **changed})


def test_ocr_key_ignores_knobs_that_cannot_change_output():
    """max_workers, timeout, retries and the API key must NOT partition: page
    concurrency is documented in ocr/config.py as output-neutral, transport
    settings are not output, and a secret must never be hashed into a key that
    is written to disk."""
    base = ocr_settings_key(ocr_settings=_OcrSettings())
    for irrelevant in (
        _OcrSettings(max_workers=8),
        _OcrSettings(timeout=5.0),
        _OcrSettings(retries=9),
        _OcrSettings(api_key="a-real-secret"),
    ):
        assert ocr_settings_key(ocr_settings=irrelevant) == base


# ---------------------------------------------------------------------------
# P20-ARTIFACTS (Phase 2.0, OQ8/OQ10/F-6) — the v5 key material
# ---------------------------------------------------------------------------


def test_extractor_is_visual_only_for_the_forced_escalation_shape():
    """The one function, pinned (`_ocr_extractor`): visual only for
    force_ocr=True AND allow_visual_ocr=True — the runner's escalation call
    shape (`discovery/runner.py::_read_visual`). Every other shape, including
    the ambiguous auto call, is "offline"."""
    from webapp.artifact_cache import _ocr_extractor

    assert _ocr_extractor(force_ocr=True, allow_local_ocr=False, allow_visual_ocr=True) == "visual"
    assert _ocr_extractor(force_ocr=False, allow_local_ocr=True, allow_visual_ocr=False) == "offline"
    assert _ocr_extractor(force_ocr=False, allow_local_ocr=False, allow_visual_ocr=False) == "offline"
    # The ambiguous "auto" shape: offline gets first refusal inside one
    # `parse_statement` call, so it is labelled offline whatever eventually
    # produces the text.
    assert _ocr_extractor(force_ocr=False, allow_local_ocr=True, allow_visual_ocr=True) == "offline"
    # force_ocr alone, without allow_visual_ocr, cannot reach the visual rung.
    assert _ocr_extractor(force_ocr=True, allow_local_ocr=False, allow_visual_ocr=False) == "offline"


def test_extractor_is_paddle_only_for_the_forced_paddle_shape():
    """P21-ROUTING (M9): the Paddle counterpart of the truth table above.
    `"paddle"` ONLY for `force_ocr=True AND allow_paddle_ocr=True` — never
    for `allow_paddle_ocr=True` alone, and never mistaken for `"visual"`."""
    from webapp.artifact_cache import _ocr_extractor

    assert _ocr_extractor(
        force_ocr=True, allow_local_ocr=False, allow_visual_ocr=False, allow_paddle_ocr=True
    ) == "paddle"
    assert _ocr_extractor(
        force_ocr=False, allow_local_ocr=False, allow_visual_ocr=False, allow_paddle_ocr=True
    ) == "offline"
    assert _ocr_extractor(
        force_ocr=True, allow_local_ocr=False, allow_visual_ocr=False, allow_paddle_ocr=False
    ) == "offline"
    # A hand-built, contract-violating call (both true) still resolves to a
    # DEFINED answer rather than an unspecified one — never "visual".
    assert _ocr_extractor(
        force_ocr=True, allow_local_ocr=False, allow_visual_ocr=True, allow_paddle_ocr=True
    ) == "paddle"


def test_postprocess_state_partitions_the_key_and_pins_the_quarantined_default():
    """`postprocess_state` / `postprocess_admitted` come from `ocr.ocr_client`
    via getattr with the pinned quarantined defaults (until B1 composes).

    Review BLOCK-2: composition order lands B1 BEFORE this cell
    (`PHASE2-0-SAFETY.md`: B2 -> B1 -> A -> C -> D), and B1 is chartered to
    add exactly `POSTPROCESS_STATE = "quarantined"` /
    `ADMITTED_POSTPROCESS = ()` to `ocr.ocr_client` — the SAME values this
    module's own defaults pin. Asserting `not hasattr(...)` is a fact about
    today's tree, not a contract, and fails the moment B1 composes even
    though nothing this cell depends on changed. Assert the VALUE instead,
    which is correct whether B1 has landed or not."""
    import ocr.ocr_client as ocr_client_module
    from webapp.artifact_cache import (
        ADMITTED_POSTPROCESS_DEFAULT,
        POSTPROCESS_STATE_DEFAULT,
        _ocr_postprocess_readout,
    )

    assert getattr(ocr_client_module, "POSTPROCESS_STATE", POSTPROCESS_STATE_DEFAULT) == "quarantined"
    assert tuple(getattr(ocr_client_module, "ADMITTED_POSTPROCESS", ADMITTED_POSTPROCESS_DEFAULT)) == ()
    assert _ocr_postprocess_readout("visual") == ("quarantined", ())
    assert _ocr_postprocess_readout("offline") == ("quarantined", ())

    class _Settings(_OcrSettings):
        pass

    visual_key = ocr_settings_key(force_ocr=True, allow_local_ocr=False, allow_visual_ocr=True,
                                  ocr_settings=_Settings())
    with unittest.mock.patch.object(ocr_client_module, "POSTPROCESS_STATE", "some-other-state", create=True):
        changed_key = ocr_settings_key(force_ocr=True, allow_local_ocr=False, allow_visual_ocr=True,
                                       ocr_settings=_Settings())
    assert visual_key != changed_key


def test_postprocess_admitted_partitions_the_visual_key():
    """The other new BLOCK-1 gap: `postprocess_admitted` must partition the
    key on its own — a visual-labelled key computed with one admitted
    function must differ from the pinned empty-tuple default. Patches
    `ADMITTED_POSTPROCESS` to a one-member tuple (`create=True`, since B1 has
    not composed on this tree)."""
    import ocr.ocr_client as ocr_client_module

    class _Settings(_OcrSettings):
        pass

    with unittest.mock.patch.object(ocr_client_module, "ADMITTED_POSTPROCESS", (), create=True):
        base = ocr_settings_key(force_ocr=True, allow_local_ocr=False, allow_visual_ocr=True,
                                ocr_settings=_Settings())
    with unittest.mock.patch.object(ocr_client_module, "ADMITTED_POSTPROCESS", ("strip_det_tags",), create=True):
        changed = ocr_settings_key(force_ocr=True, allow_local_ocr=False, allow_visual_ocr=True,
                                   ocr_settings=_Settings())
    assert base != changed


def test_postprocess_never_imports_ocr_client_for_an_offline_labelled_call():
    """The architectural property two other test files already assert for the
    whole process (`tests/test_discovery.py`, `tests/test_visual_rung.py`):
    computing an OFFLINE key must not import the model client module. Proven
    in a subprocess so a prior import elsewhere in the test session cannot
    hide a regression."""
    code = (
        "import sys;"
        "from webapp.artifact_cache import ocr_settings_key;"
        "ocr_settings_key(force_ocr=False, allow_local_ocr=True, allow_visual_ocr=False);"
        "print('ocr.ocr_client' in sys.modules)"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "False", result.stdout


def test_raster_version_partitions_the_key():
    import ocr.rasterize as rasterize_module

    base = ocr_settings_key(ocr_settings=_OcrSettings())
    # patched to a value that is never the live default (P22-IDENTITY
    # closure-2 bumped the live value to 2), so this proves the field
    # partitions regardless of what that default currently is
    with unittest.mock.patch.object(rasterize_module, "RASTER_VERSION", 999):
        changed = ocr_settings_key(ocr_settings=_OcrSettings())
    assert base != changed


def test_raster_version_is_pinned_at_2():
    """P22-IDENTITY closure-2 (review F-1): the rasteriser renders the
    CropBox (`use_cropbox=True`) so a raster and the native display frame
    share one rectangle; RASTER_VERSION 1 -> 2 lands in the same commit as
    this pin (key material for every OCR partition at v5+)."""
    from ocr.rasterize import RASTER_VERSION

    assert RASTER_VERSION == 2


def test_a_research_partition_on_a_pre_v5_stage_is_refused_not_dropped():
    """P22-IDENTITY closure-2 (review F-4): `stage_version=4` has no
    partition field; a non-empty partition there must RAISE rather than be
    silently dropped into a production-shaped key. An empty partition on a
    pre-v5 stage stays the historical key, byte for byte."""
    baseline_v4 = ocr_settings_key(ocr_settings=_OcrSettings(), stage_version=4)
    assert ocr_settings_key(ocr_settings=_OcrSettings(), stage_version=4, research_partition="") == baseline_v4
    with pytest.raises(ValueError):
        ocr_settings_key(ocr_settings=_OcrSettings(), stage_version=4, research_partition="p23-a")
    # and at v5+ the same id is accepted as its own partition
    assert ocr_settings_key(ocr_settings=_OcrSettings(), research_partition="p23-a") != ocr_settings_key(ocr_settings=_OcrSettings())


def test_raster_version_fallback_matches_the_source_module():
    """Review MINOR-1: `ocr_settings_key` falls back to a pinned duplicate
    (`_RASTER_VERSION_FALLBACK`) when `ocr.rasterize` cannot be imported
    (that module imports `pdf2image` + PIL at module level, and the offline
    key must never raise for one integer). Pins that the duplicate and the
    real constant have not drifted apart."""
    from ocr.rasterize import RASTER_VERSION
    from webapp.artifact_cache import _RASTER_VERSION_FALLBACK

    assert _RASTER_VERSION_FALLBACK == RASTER_VERSION


def test_ocr_settings_key_never_raises_when_rasterize_cannot_be_imported():
    """The actual fault this review finding names, reproduced and closed:
    `ocr.rasterize` unimportable must not raise out of `ocr_settings_key`."""
    import builtins

    real_import = builtins.__import__

    def blocking_import(name, *args, **kwargs):
        if name == "ocr.rasterize" or name.startswith("ocr.rasterize."):
            raise ModuleNotFoundError(f"No module named {name!r} (test-forced)")
        return real_import(name, *args, **kwargs)

    with unittest.mock.patch.object(builtins, "__import__", blocking_import):
        key = ocr_settings_key(force_ocr=False, allow_local_ocr=True, allow_visual_ocr=False,
                               ocr_settings=_OcrSettings())
    assert isinstance(key, str) and len(key) == 64


def test_extraction_schema_version_partitions_the_key():
    import webapp.artifact_cache as module

    base = ocr_settings_key(ocr_settings=_OcrSettings())
    # P21-ROUTING bumped the live default to 2 (D6); patch to a value that is
    # never the live default so this proves the field partitions regardless
    # of what that default currently is.
    with unittest.mock.patch.object(module, "EXTRACTION_SCHEMA_VERSION", 999):
        changed = ocr_settings_key(ocr_settings=_OcrSettings())
    assert base != changed


def test_allow_paddle_ocr_partitions_the_key():
    base = ocr_settings_key(ocr_settings=_OcrSettings())
    changed = ocr_settings_key(ocr_settings=_OcrSettings(), allow_paddle_ocr=True)
    assert base != changed


def test_paddle_labelled_key_carries_the_paddle_settings_block(monkeypatch):
    """D5/design item 5: when the extractor resolves to `"paddle"`, the key
    material carries `paddle_settings_key_material(load_paddle_settings())`
    — never the host/port/token, only the pins + provider + execution class."""
    monkeypatch.setenv("PADDLE_PROVIDER", "local")
    monkeypatch.setenv("PADDLE_EXECUTION_CLASS", "local_free")
    monkeypatch.delenv("PADDLE_REMOTE_OPT_IN", raising=False)
    key_with_paddle = ocr_settings_key(
        ocr_settings=_OcrSettings(), force_ocr=True, allow_visual_ocr=False, allow_paddle_ocr=True,
    )
    key_without = ocr_settings_key(ocr_settings=_OcrSettings())
    assert key_with_paddle != key_without

    # Changing the provider/class changes the key: the "paddle" block is real
    # key material, not a fixed placeholder.
    monkeypatch.setenv("PADDLE_PROVIDER", "vast.ai")
    monkeypatch.setenv("PADDLE_EXECUTION_CLASS", "remote_paid")
    monkeypatch.setenv("PADDLE_VAST_HOST", "test-host")
    monkeypatch.setenv("PADDLE_VAST_SSH_PORT", "22")
    monkeypatch.setenv("PADDLE_VAST_SSH_USER", "test-user")
    key_remote = ocr_settings_key(
        ocr_settings=_OcrSettings(), force_ocr=True, allow_visual_ocr=False, allow_paddle_ocr=True,
    )
    assert key_remote != key_with_paddle


def test_a_paddle_labelled_key_refuses_when_paddle_settings_cannot_load(monkeypatch):
    """The paddle-labelled key REFUSES (raises) when Paddle settings cannot
    be loaded — never a default block standing in for a real configuration."""
    from ocr.paddle_config import PaddleConfigError

    monkeypatch.delenv("PADDLE_PROVIDER", raising=False)
    monkeypatch.delenv("PADDLE_EXECUTION_CLASS", raising=False)
    with pytest.raises(PaddleConfigError):
        ocr_settings_key(
            ocr_settings=_OcrSettings(), force_ocr=True, allow_visual_ocr=False, allow_paddle_ocr=True,
        )


def test_ocr_settings_key_only_calls_load_paddle_settings_for_the_paddle_branch():
    """`ocr_settings_key`'s OWN body lazily imports/calls
    `load_paddle_settings` / `paddle_settings_key_material` ONLY inside the
    `extractor == "paddle"` branch — never derived for an offline- or
    visual-labelled call. (`ocr.paddle_config` itself is unconditionally
    importABLE process-wide — `ocr/config.py` needs `PADDLE_MODEL_TOKEN` at
    module scope for OQ2's `RESERVED_MODEL_PREFIXES` — so a process-wide
    `sys.modules` absence is not the property to check here, unlike
    `ocr.ocr_client`, which carries no such independent, always-needed
    reason to load. What matters — and what this proves — is that computing
    an offline/visual key never CALLS into Paddle settings at all.)"""
    import inspect

    import webapp.artifact_cache as module

    source = inspect.getsource(module.ocr_settings_key)
    # The paddle-settings names must appear ONLY in the source text following
    # the `if extractor == "paddle":` line.
    marker = 'if extractor == "paddle":'
    assert marker in source, "the paddle branch guard moved or was renamed"
    before, after = source.split(marker, 1)
    for name in ("load_paddle_settings", "paddle_settings_key_material"):
        assert name not in before, f"{name} referenced before the paddle-only branch"
        assert name in after, f"{name} missing from the paddle-only branch"


def test_extraction_schema_version_is_pinned_at_3():
    """P21-ROUTING M10 bumped EXTRACTION_SCHEMA_VERSION 1 -> 2 with the
    page_extractor/evidence fields; P22-IDENTITY (Phase 2.2, D5; mutant M5)
    bumps it 2 -> 3 in the SAME commit as the `native_evidence` /
    `native_evidence_sha256` fields it describes. This is that pin."""
    assert EXTRACTION_SCHEMA_VERSION == 3


def test_analysis_stage_version_is_pinned_at_22():
    """LENDER-DETECTION (2026-09-24 design, S2): classification version 5.0 moves
    lender groups and adds the flagged-position payload, and the classifier's
    registry is not key material, so ANALYSIS_STAGE_VERSION went 18 -> 19 in the
    same commit as the classifier change. The D6 clarification (classification
    5.1, 2026-09-26) changes stored rows again, so it goes 19 -> 20. The second D6
    clarification (classification 5.2, 2026-09-27: compensation memos, masked
    recipient accounts) goes 20 -> 21. The false-positive release (classification
    5.3, 2026-09-27) goes 21 -> 22. This is that pin."""
    assert ANALYSIS_STAGE_VERSION == 22


def test_paddle_model_token_is_not_in_free_models():
    """M13: remote_paid is not free — `PADDLE_MODEL_TOKEN` must never be
    added to `telemetry.prices.FREE_MODELS`; the actual cost is measured,
    never invented, and `price_for` reports it unpriced."""
    from ocr.paddle_config import PADDLE_MODEL_TOKEN
    from telemetry.prices import FREE_MODELS, price_for

    assert PADDLE_MODEL_TOKEN not in FREE_MODELS
    assert price_for(PADDLE_MODEL_TOKEN) is None


def test_toolchain_versions_never_raise_when_every_probe_fails():
    """An unobtainable binary version is the sentinel "unknown" on every
    field — never an exception out of the settings-key computation."""
    import webapp.artifact_cache as module

    module._toolchain_versions_cache = None
    with unittest.mock.patch("shutil.which", return_value=None), \
         unittest.mock.patch("fitz.VersionBind", None, create=True), \
         unittest.mock.patch("fitz.version", None, create=True):
        versions = module.ocr_toolchain_versions()
    assert versions == {
        "tesseract_version": "unknown",
        "poppler_version": "unknown",
        "pymupdf_version": "unknown",
    }


@pytest.mark.parametrize(
    "field,patched",
    [
        ("tesseract_version", {"tesseract_version": "tesseract 9.9.9", "poppler_version": "unknown",
                               "pymupdf_version": "unknown"}),
        ("poppler_version", {"tesseract_version": "unknown", "poppler_version": "pdftoppm version 9.9",
                             "pymupdf_version": "unknown"}),
        ("pymupdf_version", {"tesseract_version": "unknown", "poppler_version": "unknown",
                             "pymupdf_version": "9.9.9"}),
    ],
)
def test_each_toolchain_member_partitions_the_key_on_its_own(field, patched):
    """Review BLOCK-1: the field-drop mutation table's named killer
    (`test_toolchain_versions_never_raise_and_partition_on_unknown`, as it
    read before this fix) patched all three fields from "unknown" to
    non-"unknown" at once, so dropping any ONE of the three from the key
    dict still left two others differing and the assertion passed — a
    mutant that survives is a killer that does not kill. This test patches
    exactly ONE field per case, holding the other two at "unknown", so
    dropping THAT field from `webapp/artifact_cache.py`'s settings dict is
    what actually fails this parametrization."""
    import webapp.artifact_cache as module

    baseline = {"tesseract_version": "unknown", "poppler_version": "unknown", "pymupdf_version": "unknown"}
    with unittest.mock.patch.object(module, "_toolchain_versions_cache", baseline):
        base = ocr_settings_key(ocr_settings=_OcrSettings())
    with unittest.mock.patch.object(module, "_toolchain_versions_cache", patched):
        changed = ocr_settings_key(ocr_settings=_OcrSettings())
    assert base != changed, f"{field} does not partition the OCR settings key"


def test_toolchain_versions_are_cached_once_per_process(monkeypatch):
    import webapp.artifact_cache as module

    module._toolchain_versions_cache = None
    calls = []
    real_which = shutil.which

    def counting_which(name):
        calls.append(name)
        return real_which(name)

    monkeypatch.setattr("shutil.which", counting_which)
    module.ocr_toolchain_versions()
    module.ocr_toolchain_versions()
    # Two probes each call `which` twice (tesseract, pdftoppm); a cache that
    # actually cached would see exactly one round of calls, not two.
    assert len(calls) == 2


def test_stage_version_parameter_reconstructs_the_pre_v5_key_byte_for_byte():
    """`telemetry/run_of_record.py` reconstructs a batch-8/9 run's OCR key by
    calling this function with the run's OWN historical stage version — this
    pins that doing so reproduces the pre-P20-ARTIFACTS 9-field shape exactly,
    with none of the v5 fields, rather than today's shape stamped with
    yesterday's version number."""
    reconstructed_v4 = ocr_settings_key(
        force_ocr=False, allow_local_ocr=True, allow_visual_ocr=False,
        stage_version=4, ocr_settings=_OcrSettings(),
    )
    live_v5 = ocr_settings_key(
        force_ocr=False, allow_local_ocr=True, allow_visual_ocr=False,
        ocr_settings=_OcrSettings(),
    )
    assert OCR_STAGE_VERSION == 5
    assert reconstructed_v4 != live_v5
    # And it is stable / order-independent — recomputing it twice agrees.
    assert reconstructed_v4 == ocr_settings_key(
        force_ocr=False, allow_local_ocr=True, allow_visual_ocr=False,
        stage_version=4, ocr_settings=_OcrSettings(),
    )
    # Review MINOR-2: pin the two literals themselves, host-independently, in
    # this UNSKIPPABLE test (the only prior pin,
    # `tests/test_run_of_record.py`'s batch-9-cache comparison, is
    # `skipif`-gated on the cold cache being present and is SKIPPED in CI).
    # `_OcrSettings()`'s defaults reproduce the batch-8/9 archive's actual
    # keys exactly — measured directly against the cold cache's sole
    # distinct settings_key per (`allow_local_ocr` = True / False) mode.
    assert reconstructed_v4 == "0F25500A3CADF72305575A198086A30A0C348656976954489591A58C9E303BE7"
    reconstructed_v4_digital_mode = ocr_settings_key(
        force_ocr=False, allow_local_ocr=False, allow_visual_ocr=False,
        stage_version=4, ocr_settings=_OcrSettings(),
    )
    assert reconstructed_v4_digital_mode == "91937F817835CDAFFC67D66658625D874C58C697A16050EAAA4DBB58771BC671"


@pytest.mark.parametrize(
    "changed",
    [
        {"parse_mode": "deterministic"},
        {"analysis_settings": _AnalysisSettings(model="gemini-other")},
        {"analysis_settings": _AnalysisSettings(escalation_model="gemini-pro")},
        {"analysis_settings": _AnalysisSettings(withholding_denominator_mode="verified_revenue")},
    ],
)
def test_every_analysis_knob_partitions_the_key(changed):
    baseline = dict(parse_mode="auto", analysis_settings=_AnalysisSettings())
    assert analysis_settings_key(**baseline) != analysis_settings_key(
        **{**baseline, **changed}
    )


def test_analysis_key_ignores_the_api_key():
    assert analysis_settings_key(
        analysis_settings=_AnalysisSettings(api_key="secret")
    ) == analysis_settings_key(analysis_settings=_AnalysisSettings())


def test_report_key_partitions_on_title():
    assert report_settings_key(title="a.pdf") != report_settings_key(title="b.pdf")


# ---------------------------------------------------------------------------
# storage behavior
# ---------------------------------------------------------------------------


def test_round_trip_for_every_stage(cache):
    ocr_key = ocr_settings_key(ocr_settings=_OcrSettings())
    cache.put_ocr(content_sha256(PDF), ocr_key, _doc(pages=["one", "two"]))
    hit, document = cache.get_ocr(content_sha256(PDF), ocr_key)
    assert hit is True
    # D-3b: the stored document also carries O-3's per-page integrity records
    # (empty here — this fixture was never assessed by the ladder). P21-ROUTING
    # (D6): `page_extractor` / `evidence` join the record, empty/None for
    # every non-Paddle rung.
    # P22-IDENTITY (D5, schema 3): `native_evidence` / `native_evidence_sha256`
    # join the record, None for every read that is not the native rung's.
    assert document == {
        "model": "fake-ocr", "pages": ["one", "two"], "page_integrity": [],
        "page_extractor": [], "evidence": None,
        "native_evidence": None, "native_evidence_sha256": None,
    }

    analysis_key = analysis_settings_key(analysis_settings=_AnalysisSettings())
    cache.put_analysis(text_sha256("# md"), analysis_key, {"statement": {"bank": "B"}})
    assert cache.get_analysis(text_sha256("# md"), analysis_key) == {
        "statement": {"bank": "B"}
    }

    report_key = report_settings_key(title="s.pdf")
    cache.put_report(text_sha256("# md"), report_key, "<h1>md</h1>")
    assert cache.get_report(text_sha256("# md"), report_key) == "<h1>md</h1>"


def test_miss_returns_none_without_writing_anything(cache):
    assert cache.get_ocr(content_sha256(PDF), "NOPE") == (False, None)
    assert cache.get_analysis(text_sha256("x"), "NOPE") is None
    assert cache.storage.cache_entries() == []


def test_payload_lives_on_disk_and_not_in_sqlite(cache, data_dir):
    """Large artifacts are files; SQLite holds only the index row."""
    bulky = "LEDGER-ROW " * 5000
    key = cache.put_analysis(text_sha256("md"), "SETTINGS", {"markdown": bulky})

    row = cache.storage.cache_lookup(STAGE_ANALYSIS, key)
    assert row is not None
    path = cache.root / row["artifact_path"]
    assert path.is_file()
    assert bulky in path.read_text(encoding="utf-8")
    assert row["byte_size"] > 50_000
    # The database file itself never saw the payload.
    assert b"LEDGER-ROW LEDGER-ROW" not in (data_dir / "webapp.db").read_bytes()


def test_index_row_records_the_key_material_and_hits(cache):
    key = cache.put_analysis(text_sha256("md"), "SETTINGS", {"ok": True})
    row = cache.storage.cache_lookup(STAGE_ANALYSIS, key)
    assert row["input_sha256"] == text_sha256("md")
    assert row["settings_key"] == "SETTINGS"
    assert row["format_version"] == CACHE_FORMAT_VERSION
    assert row["hit_count"] == 0 and row["last_hit_at"] is None

    cache.get_analysis(text_sha256("md"), "SETTINGS")
    cache.get_analysis(text_sha256("md"), "SETTINGS")
    row = cache.storage.cache_lookup(STAGE_ANALYSIS, key)
    assert row["hit_count"] == 2 and row["last_hit_at"]


def test_stats_reports_entries_bytes_and_hits(cache):
    cache.put_analysis(text_sha256("md"), "SETTINGS", {"ok": True})
    cache.put_report(text_sha256("md"), "SETTINGS", "<p>x</p>")
    cache.get_analysis(text_sha256("md"), "SETTINGS")

    stats = cache.stats()
    assert stats[STAGE_ANALYSIS]["entries"] == 1
    assert stats[STAGE_ANALYSIS]["hits"] == 1
    assert stats[STAGE_ANALYSIS]["bytes"] > 0
    assert stats[STAGE_REPORT]["entries"] == 1
    assert stats[STAGE_REPORT]["hits"] == 0


def test_cache_survives_a_restart(data_dir):
    cache = ArtifactCache(Storage(data_dir))
    ocr_key = ocr_settings_key(ocr_settings=_OcrSettings())
    cache.put_ocr(content_sha256(PDF), ocr_key, _doc(pages=["persisted"]))
    del cache

    reopened = _reopen(data_dir)
    hit, document = reopened.get_ocr(content_sha256(PDF), ocr_key)
    assert hit is True
    assert document["pages"] == ["persisted"]


def test_a_vanished_payload_file_is_a_miss_and_self_heals(cache):
    key = cache.put_analysis(text_sha256("md"), "SETTINGS", {"ok": True})
    path = cache.root / cache.storage.cache_lookup(STAGE_ANALYSIS, key)["artifact_path"]
    path.unlink()

    assert cache.get_analysis(text_sha256("md"), "SETTINGS") is None
    # The dangling index row is dropped rather than left to miss forever.
    assert cache.storage.cache_lookup(STAGE_ANALYSIS, key) is None


def test_a_corrupt_payload_file_is_a_miss(cache):
    key = cache.put_analysis(text_sha256("md"), "SETTINGS", {"ok": True})
    path = cache.root / cache.storage.cache_lookup(STAGE_ANALYSIS, key)["artifact_path"]
    path.write_text("{not json", encoding="utf-8")

    assert cache.get_analysis(text_sha256("md"), "SETTINGS") is None
    assert cache.storage.cache_lookup(STAGE_ANALYSIS, key) is None


def test_a_payload_from_another_cache_format_is_a_miss(cache):
    key = cache.put_analysis(text_sha256("md"), "SETTINGS", {"ok": True})
    path = cache.root / cache.storage.cache_lookup(STAGE_ANALYSIS, key)["artifact_path"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["cache_format"] = CACHE_FORMAT_VERSION + 1
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert cache.get_analysis(text_sha256("md"), "SETTINGS") is None


def test_open_cache_uses_the_webapp_data_dir_convention(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_DATA_DIR", str(tmp_path / "env-dir"))
    cache = open_cache()
    assert cache.root == tmp_path / "env-dir" / "artifacts"
    # An explicit directory still wins, so a CLI run can point elsewhere.
    assert open_cache(tmp_path / "explicit").root == tmp_path / "explicit" / "artifacts"


def test_artifact_cache_refuses_ambiguous_construction(data_dir):
    with pytest.raises(ValueError):
        ArtifactCache(Storage(data_dir), data_dir=data_dir)


# ---------------------------------------------------------------------------
# memoizing wrappers (the API the CLI consumers call)
# ---------------------------------------------------------------------------


def test_cached_ocr_computes_once_then_serves_from_the_cache(cache):
    calls = []

    def compute():
        calls.append(1)
        return _doc(pages=["ledger"])

    first = cached_ocr(PDF, compute=compute, cache=cache, source_file="s.pdf")
    assert first.cached is False and len(calls) == 1

    second = cached_ocr(PDF, compute=compute, cache=cache, source_file="s.pdf")
    assert second.cached is True
    assert len(calls) == 1
    assert second.value.pages == ["ledger"]
    assert second.value.model == "fake-ocr"


def test_cached_ocr_restamps_the_source_file_instead_of_keying_on_it(cache):
    """A duplicate uploaded under a new name must still skip OCR, and the
    markdown header must name the file being processed NOW."""
    calls = []

    def compute():
        calls.append(1)
        return _doc(pages=["ledger"], source_file="original.pdf")

    cached_ocr(PDF, compute=compute, cache=cache, source_file="original.pdf")
    renamed = cached_ocr(PDF, compute=compute, cache=cache, source_file="copy.pdf")

    assert renamed.cached is True and len(calls) == 1
    assert renamed.value.source_file == "copy.pdf"
    assert "source: copy.pdf" in renamed.value.to_markdown()


def test_cached_ocr_partitions_on_the_capability_flags(cache):
    calls = []

    def compute():
        calls.append(1)
        return _doc()

    cached_ocr(PDF, compute=compute, cache=cache, allow_visual_ocr=False)
    cached_ocr(PDF, compute=compute, cache=cache, allow_visual_ocr=True)
    # Different rung, different artifact — the second read must not be served
    # the first one's text.
    assert len(calls) == 2


def test_cached_ocr_caches_a_negative_result(cache):
    """The deterministic preflight returning None is a deterministic outcome
    of the same bytes and settings; re-running the offline rungs for it would
    re-pay local Tesseract on every re-upload."""
    calls = []

    def compute():
        calls.append(1)
        return None

    first = cached_ocr(PDF, compute=compute, cache=cache, allow_visual_ocr=False)
    second = cached_ocr(PDF, compute=compute, cache=cache, allow_visual_ocr=False)
    assert first.value is None and second.value is None
    assert second.cached is True
    assert len(calls) == 1

    # D-3b: the artifact shape gained page_integrity — a negative result still
    # stores a null document rather than an empty one, and still round-trips.
    settings_key = ocr_settings_key(allow_visual_ocr=False)
    hit, document = cache.get_ocr(content_sha256(PDF), settings_key)
    assert (hit, document) == (True, None)


# ---------------------------------------------------------------------------
# P21-ROUTING closure (MAJOR-1): the D6 artifact-record contract, pinned.
# The three tests the card names — round-trip with sha reproduction; a
# drifted cached copy is a MISS with a finding, never served, never raised;
# a schema-1 record (no page_extractor/evidence keys at all) still loads.
# ---------------------------------------------------------------------------


def test_cached_ocr_round_trips_evidence_and_reproduces_its_sha(cache):
    doc = _doc_with_evidence()
    calls = []

    def compute():
        calls.append(1)
        return doc

    first = cached_ocr(PDF, compute=compute, cache=cache, source_file="s.pdf")
    assert first.cached is False
    assert first.finding is None

    second = cached_ocr(PDF, compute=compute, cache=cache, source_file="s.pdf")
    assert second.cached is True
    assert second.finding is None
    assert len(calls) == 1  # never recomputed
    assert second.value.page_extractor == doc.page_extractor
    assert second.value.evidence is not None
    # the sha reproduces byte-for-byte across the JSON round-trip
    assert second.value.evidence.evidence_sha256 == doc.evidence.evidence_sha256
    assert second.value.evidence.page_texts() == doc.evidence.page_texts()


def test_cached_ocr_treats_a_drifted_evidence_blob_as_a_miss_with_a_finding(cache):
    """MAJOR-1 / RX1 / RX2. A stored artifact whose `pages` no longer agrees
    with its own stored `evidence` (corrupted independently of this cell's
    own write path, e.g. by an out-of-band edit or a future schema mistake)
    must never be served: `cached_ocr` recomputes, and the recompute is
    marked with `finding=CACHE_FINDING_EVIDENCE_DRIFT` so the fact that a
    drift happened is not indistinguishable from an ordinary miss once the
    recompute overwrites the drifted entry."""
    doc = _doc_with_evidence(text="hello world")
    input_sha = content_sha256(PDF)
    settings_key = ocr_settings_key()
    cache.put_ocr(input_sha, settings_key, doc)

    # Corrupt the stored artifact directly: rewrite `pages` so it disagrees
    # with the stored `evidence` — the exact drift shape MAJOR-1 exists for.
    key = cache_key(STAGE_OCR, input_sha, settings_key)
    path = cache._artifact_path(STAGE_OCR, key)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["artifact"]["document"]["pages"] = ["a completely different page"]
    path.write_text(json.dumps(payload), encoding="utf-8")

    calls = []

    def compute():
        calls.append(1)
        return _doc(pages=["freshly recomputed"])

    result = cached_ocr(PDF, compute=compute, cache=cache, source_file="s.pdf")
    assert result.cached is False  # never served
    assert len(calls) == 1  # recomputed exactly once
    assert result.value.pages == ["freshly recomputed"]
    assert result.finding == CACHE_FINDING_EVIDENCE_DRIFT

    # And the drifted entry is gone: the cache now holds the fresh compute.
    hit, document = cache.get_ocr(input_sha, settings_key)
    assert hit is True
    assert document["pages"] == ["freshly recomputed"]


def test_cached_ocr_loads_a_schema_1_record_as_empty_page_extractor_and_none_evidence(cache):
    """CASE 19: the replay reads schema-1 records (no `page_extractor` /
    `evidence` keys at all — every archive entry before D6) and must still
    load them, restoring `page_extractor=[]` / `evidence=None` rather than
    raising or treating the absence itself as a drift."""
    input_sha = content_sha256(PDF)
    settings_key = ocr_settings_key()
    cache.put(STAGE_OCR, input_sha, settings_key, {
        "document": {
            "model": "local-tesseract-ocr", "pages": ["legacy page"], "page_integrity": [],
        }
        # deliberately no "page_extractor" / "evidence" keys: the schema-1 shape
    })

    def compute():
        pytest.fail("a schema-1 record is a valid hit; it must never be recomputed")

    result = cached_ocr(PDF, compute=compute, cache=cache, source_file="s.pdf")
    assert result.cached is True
    assert result.finding is None
    assert result.value.pages == ["legacy page"]
    assert result.value.page_extractor == []
    assert result.value.evidence is None


def _drift_stored_entry(cache, input_sha: str, settings_key: str) -> None:
    key = cache_key(STAGE_OCR, input_sha, settings_key)
    path = cache._artifact_path(STAGE_OCR, key)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["artifact"]["document"]["pages"] = ["drifted"]
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_cached_ocr_attaches_the_drift_finding_to_a_failed_recompute(cache):
    """P21-ROUTING closure-2 (MINOR-D). A drift was detected and the
    recompute then RAISES: no `CacheResult` exists, so the finding rides on
    the exception — `cache_finding_of(exc) == CACHE_FINDING_EVIDENCE_DRIFT`
    — while the exception's type and message are untouched. The drifted
    entry is NOT overwritten (nothing was computed): it is found again, and
    reported again, on the next call. Reproduced at 97ab9cb: the exception
    carried nothing and the drift was lost with the failed read."""
    from webapp.artifact_cache import cache_finding_of

    input_sha = content_sha256(PDF)
    settings_key = ocr_settings_key()
    cache.put_ocr(input_sha, settings_key, _doc_with_evidence())
    _drift_stored_entry(cache, input_sha, settings_key)

    def failing_compute():
        raise RuntimeError("worker unreachable")

    with pytest.raises(RuntimeError) as caught:
        cached_ocr(PDF, compute=failing_compute, cache=cache, source_file="s.pdf")
    assert cache_finding_of(caught.value) == CACHE_FINDING_EVIDENCE_DRIFT
    assert str(caught.value) == "worker unreachable"  # type and message untouched

    # the drifted entry is still there — never served, found again next time
    hit, document = cache.get_ocr(input_sha, settings_key)
    assert hit is True and document["pages"] == ["drifted"]
    with pytest.raises(RuntimeError) as again:
        cached_ocr(PDF, compute=failing_compute, cache=cache, source_file="s.pdf")
    assert cache_finding_of(again.value) == CACHE_FINDING_EVIDENCE_DRIFT

    # and a recompute that then SUCCEEDS reports the same drift on its CacheResult
    result = cached_ocr(PDF, compute=lambda: _doc(pages=["fresh"]), cache=cache, source_file="s.pdf")
    assert result.finding == CACHE_FINDING_EVIDENCE_DRIFT and result.cached is False


def test_cached_ocr_attaches_no_finding_to_a_failed_compute_without_a_drift(cache):
    """The negative control for the test above: an ordinary miss whose
    compute raises carries NO finding — `cache_finding_of` is `None`."""
    from webapp.artifact_cache import cache_finding_of

    def failing_compute():
        raise RuntimeError("worker unreachable")

    with pytest.raises(RuntimeError) as caught:
        cached_ocr(PDF, compute=failing_compute, cache=cache, source_file="s.pdf")
    assert cache_finding_of(caught.value) is None
    assert cache_finding_of(RuntimeError("bare")) is None


def test_cached_analysis_computes_once_and_partitions_on_settings(cache):
    calls = []

    def compute():
        calls.append(1)
        return {"statement": {"bank": "Test Bank"}}

    first = cached_analysis(
        "# md", compute=compute, cache=cache, parse_mode="auto",
        analysis_settings=_AnalysisSettings(),
    )
    second = cached_analysis(
        "# md", compute=compute, cache=cache, parse_mode="auto",
        analysis_settings=_AnalysisSettings(),
    )
    assert first.cached is False and second.cached is True
    assert second.value == {"statement": {"bank": "Test Bank"}}
    assert len(calls) == 1

    # A changed extraction model re-analyzes rather than serving the old model's
    # answer.
    third = cached_analysis(
        "# md", compute=compute, cache=cache, parse_mode="auto",
        analysis_settings=_AnalysisSettings(model="gemini-other"),
    )
    assert third.cached is False and len(calls) == 2


def test_the_sheet_partition_is_analysis_key_material(cache):
    """The collision W3 §WIRING W3 demonstrated, refused.

    Two page lists of the SAME LENGTH that render to the SAME admissible
    markdown, with opposite answers on `missing_declared_statement_page`: the
    second sheet of A carries a forged separator line, so splitting the text
    puts the boundary somewhere the intake object never had one. Keying on the
    text — or on the text plus a sheet COUNT — serves A's cached answer for B.
    """
    separator = "--- Page 2 ---"
    a = ["Page 2 of 2\nalpha", f"Page 2 of 2\nbeta\n\n{separator}\n\ngamma"]
    b = [f"Page 2 of 2\nalpha\n\n{separator}\n\nPage 2 of 2\nbeta", "gamma"]
    markdown = StatementMarkdown(source_file="s.pdf", model="m", pages=a).to_markdown()
    assert markdown == StatementMarkdown(
        source_file="s.pdf", model="m", pages=b
    ).to_markdown(), "the fixture must render both partitions to one string"
    assert len(a) == len(b), "the fixture must hold the sheet COUNT equal"

    calls = []

    def compute():
        calls.append(1)
        return {"sheets": len(calls)}

    first = cached_analysis(
        markdown, compute=compute, cache=cache, parse_mode="deterministic",
        analysis_settings=_AnalysisSettings(), sheets=a,
    )
    second = cached_analysis(
        markdown, compute=compute, cache=cache, parse_mode="deterministic",
        analysis_settings=_AnalysisSettings(), sheets=b,
    )
    assert first.cached is False and second.cached is False, (
        "two partitions of one markdown must not share an analysis entry"
    )
    assert len(calls) == 2
    assert analysis_input_sha(markdown, a) != analysis_input_sha(markdown, b)
    assert sheets_sha256(a) != sheets_sha256(b)


def test_no_sheet_list_is_a_different_key_from_a_sheet_list(cache):
    """Absence is a fact, not an empty partition.

    A caller with no intake object gets the fail-closed analysis, and that
    answer must never be served to a caller that proved page structure — nor
    the other way round.
    """
    markdown = StatementMarkdown(
        source_file="s.pdf", model="m", pages=["one"]
    ).to_markdown()
    assert sheets_sha256(None) is None
    assert sheets_sha256([]) is not None
    keys = {
        analysis_input_sha(markdown, None),
        analysis_input_sha(markdown, []),
        analysis_input_sha(markdown, ["one"]),
    }
    assert len(keys) == 3


def test_passing_the_document_text_as_the_sheet_list_is_refused_by_the_cache():
    """The same call-site footgun `assess_document_integrity` refuses.

    `str` is a `Sequence[str]`, so `sheets=markdown` type-checks and then
    iterates one character per sheet. In the analysis it clears a
    fraud-relevant flag; here it would partition the cache on nonsense while
    looking like evidence.
    """
    with pytest.raises(TypeError, match="not the document text"):
        sheets_sha256("--- Page 1 ---\nrows")


def test_a_one_shot_iterable_of_sheets_is_refused():
    """Hashing consumes it, and the caller then analyses an empty sequence.

    The analysis fail-closes on that, so the ANSWER is conservative — but it is
    stored under the key of a partition that was proven, so a later caller
    supplying the same pages properly is served the fail-closed result. Nothing
    in the payload looks wrong, which is exactly why this is a refusal and not
    a docstring note.
    """
    pages = ["Page 1 of 2\nalpha", "beta"]
    for one_shot in ((page for page in pages), iter(pages), map(str, pages)):
        with pytest.raises(TypeError, match="one-shot iterable"):
            sheets_sha256(one_shot)
    # ...and the sequences a real caller has keep working.
    assert sheets_sha256(pages) == sheets_sha256(tuple(pages))


def test_a_non_string_sheet_is_refused_by_name():
    """An `AttributeError` from inside the digest names nothing; this names the
    index, which is the only thing that identifies the offending call site."""
    with pytest.raises(TypeError, match=r"sheets\[1\] is int"):
        sheets_sha256(["Page 1 of 2\nalpha", 2])


def test_sheet_order_is_key_material_and_that_is_deliberate():
    """Over-partitioning, in the direction this module's contract calls safe.

    Three sheets have six permutations and six keys for one answer. It costs a
    recompute and never serves a stale artifact, and it is unreachable in
    production anyway: the markdown is rendered from the same ordered list that
    is hashed here.
    """
    pages = ["one", "two", "three"]
    permutations = [
        [pages[i], pages[j], pages[k]]
        for i in range(3) for j in range(3) for k in range(3)
        if len({i, j, k}) == 3
    ]
    assert len(permutations) == 6
    assert len({sheets_sha256(order) for order in permutations}) == 6


def test_cached_analysis_never_caches_a_failure(cache):
    calls = []

    def boom():
        calls.append(1)
        raise RuntimeError("no deterministic parser matched this statement")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            cached_analysis("# md", compute=boom, cache=cache,
                            analysis_settings=_AnalysisSettings())
    assert len(calls) == 2
    assert cache.storage.cache_entries(STAGE_ANALYSIS) == []


def test_cached_report_computes_once(cache):
    calls = []

    def compute():
        calls.append(1)
        return "<h1>md</h1>"

    assert cached_report("# md", compute=compute, cache=cache, title="s.pdf").cached is False
    again = cached_report("# md", compute=compute, cache=cache, title="s.pdf")
    assert again.cached is True and again.value == "<h1>md</h1>"
    assert len(calls) == 1


def test_cache_none_disables_caching_entirely(tmp_path):
    calls = []

    def compute():
        calls.append(1)
        return _doc()

    for _ in range(3):
        result = cached_ocr(PDF, compute=compute, cache=None)
        assert result.cached is False and result.cache_key is None
    assert len(calls) == 3


def test_stages_are_independent(cache):
    """The point of keying the analysis stage on the MARKDOWN hash: changing
    an analysis knob re-analyzes without re-reading the document."""
    ocr_calls, analysis_calls = [], []

    def read():
        ocr_calls.append(1)
        return _doc(pages=["ledger"])

    def analyze():
        analysis_calls.append(1)
        return {"statement": {"bank": "Test Bank"}}

    def cycle(analysis_settings):
        document = cached_ocr(PDF, compute=read, cache=cache, source_file="s.pdf").value
        cached_analysis(
            document.to_markdown(), compute=analyze, cache=cache,
            analysis_settings=analysis_settings,
        )

    cycle(_AnalysisSettings())
    cycle(_AnalysisSettings())
    assert (len(ocr_calls), len(analysis_calls)) == (1, 1)

    cycle(_AnalysisSettings(model="gemini-other"))
    # Re-analyzed, NOT re-read.
    assert (len(ocr_calls), len(analysis_calls)) == (1, 2)


# ---------------------------------------------------------------------------
# the hard requirement, proven through the real worker
# ---------------------------------------------------------------------------


class _CallCounter:
    """Counts every OCR-ladder and analysis-pipeline invocation. Any nonzero
    delta on a re-run of identical bytes fails the D-3 acceptance criterion."""

    def __init__(self) -> None:
        self.ocr = 0
        self.analysis = 0

    def install(self, monkeypatch, pages=("ledger page",)) -> None:
        def fake_parse(pdf_bytes, source_file="", **kwargs):
            self.ocr += 1
            # Different bytes must produce different TEXT, as the real ladder
            # does. Since W3 FILENAME-BOUNDARY the analysis stage keys on the
            # filename-free markdown, so a stub that returned one fixed page for
            # every PDF would make two genuinely different documents share one
            # analysis input — and the distinct-documents assertion below would
            # be measuring the stub rather than the cache. (Before the boundary
            # it passed only because the filename was still in the key.)
            return StatementMarkdown(
                source_file=source_file,
                model="fake-ocr",
                pages=[*pages, f"document {content_sha256(pdf_bytes)[:16]}"],
            )

        def fake_analyze(markdown, parse_mode="auto", **kwargs):
            self.analysis += 1
            return object()

        monkeypatch.setattr("webapp.worker.parse_statement", fake_parse)
        monkeypatch.setattr("webapp.worker.analyze_document", fake_analyze)
        monkeypatch.setattr(
            "webapp.worker.document_to_json",
            lambda document: {"statement": {"bank": "Test Bank"},
                            "quality": {"level": "transaction_level"}},
        )


def _run(store: JobStore, filename="s.pdf", pdf_bytes=PDF, **kwargs):
    job = store.create(filename, pdf_bytes=pdf_bytes)
    run_job(job.id, pdf_bytes, filename, store, **kwargs)
    return store.get(job.id)


def test_reupload_of_identical_bytes_performs_zero_ocr_and_zero_llm_calls(
    monkeypatch, data_dir
):
    counter = _CallCounter()
    counter.install(monkeypatch)
    store = JobStore(Storage(data_dir))

    first = _run(store)
    assert (counter.ocr, counter.analysis) == (1, 1)
    assert first.status == "done"

    second = _run(store)
    # THE acceptance criterion: not one further call.
    assert (counter.ocr, counter.analysis) == (1, 1)
    assert second.status == "done"
    assert second.markdown == first.markdown
    assert second.html == first.html
    assert second.analysis == first.analysis
    assert second.parse_model == first.parse_model


def test_cached_reprocessing_survives_a_restart(monkeypatch, data_dir):
    counter = _CallCounter()
    counter.install(monkeypatch)

    first = _run(JobStore(Storage(data_dir)))
    assert (counter.ocr, counter.analysis) == (1, 1)

    # Tear down and reopen over the same data directory — a process restart.
    restarted = JobStore(Storage(data_dir))
    second = _run(restarted)
    assert (counter.ocr, counter.analysis) == (1, 1)
    assert second.markdown == first.markdown
    assert second.analysis == first.analysis


def test_distinct_bytes_are_never_served_from_another_documents_cache(
    monkeypatch, data_dir
):
    counter = _CallCounter()
    counter.install(monkeypatch)
    store = JobStore(Storage(data_dir))

    _run(store, filename="a.pdf", pdf_bytes=PDF)
    _run(store, filename="b.pdf", pdf_bytes=OTHER_PDF)
    assert (counter.ocr, counter.analysis) == (2, 2)


def test_changed_analysis_settings_reanalyze_without_reocr(monkeypatch, data_dir):
    counter = _CallCounter()
    counter.install(monkeypatch)
    store = JobStore(Storage(data_dir))

    _run(store)
    assert (counter.ocr, counter.analysis) == (1, 1)

    # A different extraction model must not be served the old model's answer —
    # but it must not re-OCR either.
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-pro-experiment")
    _run(store)
    assert (counter.ocr, counter.analysis) == (1, 2)


def test_a_cache_hit_still_fills_the_live_viewer_buffer(monkeypatch, data_dir):
    counter = _CallCounter()
    counter.install(monkeypatch, pages=("ledger page",))
    store = JobStore(Storage(data_dir))

    _run(store)
    job = _run(store)
    assert counter.ocr == 1
    # Nothing was OCR'd, yet the viewer's live panel still has the pages.
    assert "ledger page" in store.get(job.id).live_text


def test_cache_hits_are_audit_logged(monkeypatch, data_dir):
    counter = _CallCounter()
    counter.install(monkeypatch)
    store = JobStore(Storage(data_dir))

    _run(store)
    assert store.storage.audit_events("cache_hit") == []

    second = _run(store)
    events = store.storage.audit_events("cache_hit", job_id=second.id)
    stages = {json.loads(event["detail"])["stage"] for event in events}
    assert stages == {STAGE_OCR, STAGE_ANALYSIS, STAGE_REPORT}


def test_the_index_is_a_derived_cache_not_an_append_only_ledger(cache):
    """Unlike review_decisions/audit_log, artifact_cache rows may be updated
    and deleted — it holds nothing that is not recomputable."""
    key = cache.put_analysis(text_sha256("md"), "SETTINGS", {"ok": True})
    with sqlite3.connect(cache.storage.db_path) as conn:
        conn.execute(
            "UPDATE artifact_cache SET hit_count = 5 WHERE cache_key = ?", (key,)
        )
        conn.execute("DELETE FROM artifact_cache WHERE cache_key = ?", (key,))
    assert cache.storage.cache_lookup(STAGE_ANALYSIS, key) is None


# ---------------------------------------------------------------------------
# D-3b: O-3 page-integrity flags survive the cache
# ---------------------------------------------------------------------------


def _flagged_doc() -> StatementMarkdown:
    """Two pages: one clean, one truncated with both evidence classes."""
    return StatementMarkdown(
        source_file="scan.pdf",
        model="fake-ocr",
        pages=["clean page", "<table><tr><td>cut off"],
        page_integrity=[
            PageIntegrity(page_index=0, truncated=False, signals=[], finish_reason="stop"),
            PageIntegrity(
                page_index=1,
                truncated=True,
                signals=["model_finish_reason_length", "open_table_at_tail"],
                finish_reason="length",
            ),
        ],
    )


def test_cached_ocr_preserves_o3_page_integrity(cache):
    """A cached read must be indistinguishable from a fresh one: dropping the
    truncation flags would turn an intake defect back into a silent one."""
    fresh = _flagged_doc()
    calls = []

    def compute():
        calls.append(1)
        return fresh

    cached_ocr(PDF, compute=compute, cache=cache, source_file="scan.pdf")
    served = cached_ocr(PDF, compute=compute, cache=cache, source_file="scan.pdf")

    assert served.cached is True and len(calls) == 1
    document = served.value
    assert document.has_truncated_pages is True
    assert document.truncated_pages == fresh.truncated_pages == [1]
    assert [item.to_dict() for item in document.page_integrity] == [
        item.to_dict() for item in fresh.page_integrity
    ]
    # Field by field, so a partial reconstruction cannot pass on the dict alone.
    clean, truncated = document.page_integrity
    assert (clean.page_index, clean.truncated, clean.signals, clean.finish_reason) == (
        0, False, [], "stop",
    )
    assert truncated.page_index == 1 and truncated.truncated is True
    assert truncated.signals == [
        "model_finish_reason_length", "open_table_at_tail",
    ]
    assert truncated.finish_reason == "length"
    assert all(isinstance(item, PageIntegrity) for item in document.page_integrity)
    # And nothing else about the document moved.
    assert document.pages == fresh.pages and document.model == fresh.model


def test_a_document_without_integrity_records_round_trips_as_unassessed(cache):
    """An empty page_integrity means "the ladder did not assess this" and must
    stay empty rather than being invented on read."""
    cached_ocr(PDF, compute=lambda: _doc(pages=["a"]), cache=cache)
    served = cached_ocr(PDF, compute=lambda: pytest.fail("must be cached"), cache=cache)
    assert served.value.page_integrity == []
    assert served.value.has_truncated_pages is False


def test_a_document_shaped_object_without_the_o3_field_still_stores(cache):
    """O-3's own readers tolerate objects that predate the field (its test
    doubles return plain strings); the cache does the same rather than
    raising on a hand-built extractor result."""

    class _PreO3Doc:
        model = "legacy-extractor"
        pages = ["only a page list and a model"]

    cache.put_ocr(content_sha256(PDF), "SETTINGS", _PreO3Doc())
    hit, document = cache.get_ocr(content_sha256(PDF), "SETTINGS")
    assert hit is True
    assert document["page_integrity"] == []


def test_the_ocr_stage_version_bump_invalidates_pre_o3_entries(cache, monkeypatch):
    """The standing stage-version criterion, exercised: an artifact written
    under the pre-O-3 shape (v1) must MISS under v2 rather than be served
    without its truncation flags.

    The two versions below stay 1 and 2 deliberately — that pair is the
    historical case the criterion was written for, and re-pointing it at
    whatever the current version happens to be would test a moving target
    instead of a known one. The assertion on the live constant is separate,
    and is what makes a bump land here for a decision rather than silently.
    """
    import webapp.artifact_cache as module

    # Pinned. 1 -> 2: D-3b, O-3's page_integrity joined the OCR artifact.
    # 2 -> 3: GEOM-1, the native rung's Woodforest column read appends a block
    # to that family's markdown, and a v2 entry would keep serving the
    # flattened text the block exists to replace.
    # 3 -> 4: DESC-COLUMNS (batch-8 train), the native rung's printed-row
    # extraction behind the fail-closed furniture gate rotates the analysis
    # input of the core-processor complex; a v3 entry would keep serving the
    # pre-rung markdown. Global, like v3; the cold run re-reads the archive.
    # 4 -> 5: P20-ARTIFACTS (Phase 2.0 — OQ8/OQ10/F-6): the key gains
    # `extractor`, `postprocess_state` + `postprocess_admitted`,
    # `raster_version`, `extraction_schema_version`, `endpoint_class` and the
    # Tesseract/Poppler/PyMuPDF binary versions. No extractor's OUTPUT
    # changed and the artifact shape did not change either
    # (`CACHE_FORMAT_VERSION` stays 1); GLOBAL by construction, as v2-v4
    # were — the Phase 2.0 cold run re-reads the archive; vendor cost $0.00.
    assert OCR_STAGE_VERSION == 5
    calls = []

    def compute():
        calls.append(1)
        return _flagged_doc()

    monkeypatch.setattr(module, "OCR_STAGE_VERSION", 1)
    assert cached_ocr(PDF, compute=compute, cache=cache).cached is False
    assert cached_ocr(PDF, compute=compute, cache=cache).cached is True
    assert len(calls) == 1

    monkeypatch.setattr(module, "OCR_STAGE_VERSION", 2)
    under_v2 = cached_ocr(PDF, compute=compute, cache=cache)
    assert under_v2.cached is False and len(calls) == 2
    # The v1 entry is still on disk under its own key — invalidated, not
    # corrupted, and it never leaks into a v2 read.
    assert len(cache.storage.cache_entries(STAGE_OCR)) == 2


def test_stage_version_constants_are_part_of_the_settings_keys():
    """Code changes are invisible to a content hash; the stage version is the
    only lever that invalidates artifacts after a pipeline change, so it must
    actually be in the key."""
    import webapp.artifact_cache as module

    before = analysis_settings_key(analysis_settings=_AnalysisSettings())
    original = module.ANALYSIS_STAGE_VERSION
    try:
        module.ANALYSIS_STAGE_VERSION = original + 1
        assert analysis_settings_key(analysis_settings=_AnalysisSettings()) != before
    finally:
        module.ANALYSIS_STAGE_VERSION = original
    assert ANALYSIS_STAGE_VERSION == original


# ---------------------------------------------------------------------------
# P22-IDENTITY (Phase 2.2, cell K): D5 — native evidence persisted with its
# sha (case 13); D6 — the geometry-aware analysis key (case 12); D7 — the
# research partition in the OCR key (case 17's key half).
# ---------------------------------------------------------------------------


def _native_evidence(page_count: int, *, salt: str = "") -> ExtractionEvidence:
    """A native-shaped evidence (`native-pdf-words`, pdf_point frames, no
    raw/confidence/line_ref) with `page_count` pages. The words deliberately
    do NOT spell the document's page strings: `native_evidence` requires the
    page COUNT to agree, never the text."""
    pages = []
    for index in range(page_count):
        frame = PageFrame.pdf_points(page_index=index, width_pt=612.0, height_pt=792.0)
        word = WordBox(word_id=f"p{index}.l-.w0", page_index=index, text=f"WORD{index}{salt}",
                       x0=72.0, y0=100.0, x1=120.0, y1=112.0)
        pages.append(PageEvidence(frame=frame, words=(word,)))
    return ExtractionEvidence(
        document_sha256="C" * 64, extractor_id="native-pdf-words", model_token="native-pdf-words",
        pages=tuple(pages), runtime={"pymupdf_version": "test", "frame": "display"},
    )


def _doc_with_native_evidence(pages=("native page one", "native page two"), salt: str = "") -> StatementMarkdown:
    return StatementMarkdown(
        source_file="s.pdf", model="native-pdf-text", pages=list(pages),
        page_extractor=["native-pdf-text"] * len(pages),
        native_evidence=_native_evidence(len(pages), salt=salt),
    )


def test_native_evidence_requires_the_page_count_to_agree_but_never_the_text():
    """D5's asymmetry: the native page strings come from PyMuPDF text blocks,
    the evidence from word grouping — they need not be equal; the page count
    must be."""
    doc = _doc_with_native_evidence()
    assert doc.native_evidence.page_texts() != doc.pages
    assert doc.native_evidence_sha256 == doc.native_evidence.evidence_sha256
    assert _doc().native_evidence_sha256 is None
    from ocr.config import ProvenanceTokenError

    with pytest.raises(ProvenanceTokenError):
        StatementMarkdown(source_file="s.pdf", model="native-pdf-text", pages=["only one"],
                          native_evidence=_native_evidence(2))
    with pytest.raises(ProvenanceTokenError):
        StatementMarkdown(source_file="s.pdf", model="native-pdf-text", pages=["a"], native_evidence="nope")


def test_native_evidence_does_not_change_a_single_markdown_byte():
    """M14: `to_markdown()` is pinned by the committed corpus artifacts; here
    the same pages with and without native evidence render identically."""
    with_evidence = _doc_with_native_evidence()
    without = StatementMarkdown(source_file="s.pdf", model="native-pdf-text",
                                pages=list(with_evidence.pages), page_extractor=list(with_evidence.page_extractor))
    assert with_evidence.to_markdown() == without.to_markdown()


def test_cached_ocr_round_trips_native_evidence_and_reproduces_its_sha_byte_for_byte(cache):
    """CASE 13: a native read's OCR record carries `native_evidence` with its
    sha; a cache hit reproduces the sha byte-for-byte and the object equal."""
    doc = _doc_with_native_evidence()
    calls = []

    def compute():
        calls.append(1)
        return doc

    first = cached_ocr(PDF, compute=compute, cache=cache, source_file="s.pdf")
    assert first.cached is False and first.finding is None
    hit, record = cache.get_ocr(content_sha256(PDF), ocr_settings_key())
    assert hit is True
    assert record["native_evidence_sha256"] == doc.native_evidence_sha256
    assert record["native_evidence"]["evidence_sha256"] == doc.native_evidence_sha256
    assert record["evidence"] is None  # the sibling field stays None for the native rung

    second = cached_ocr(PDF, compute=compute, cache=cache, source_file="s.pdf")
    assert second.cached is True and second.finding is None and len(calls) == 1
    assert second.value.native_evidence == doc.native_evidence
    assert second.value.native_evidence_sha256 == doc.native_evidence_sha256
    assert second.value.evidence is None
    assert second.value.to_markdown() == doc.to_markdown()


def test_a_native_evidence_whose_stored_sha_does_not_match_is_a_miss_with_a_finding(cache):
    """M6: a restore must re-verify the blob against the sha the RECORD
    claims (`native_evidence_sha256`), not only against the sha the blob
    reproduces on its own. A tampered sidecar sha is a drift: miss, finding,
    recompute — never served."""
    input_sha = content_sha256(PDF)
    settings_key = ocr_settings_key()
    cache.put_ocr(input_sha, settings_key, _doc_with_native_evidence())
    key = cache_key(STAGE_OCR, input_sha, settings_key)
    path = cache._artifact_path(STAGE_OCR, key)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["artifact"]["document"]["native_evidence_sha256"] = "0" * 64  # the blob itself is intact
    path.write_text(json.dumps(payload), encoding="utf-8")

    calls = []

    def compute():
        calls.append(1)
        return _doc_with_native_evidence(salt="fresh")

    result = cached_ocr(PDF, compute=compute, cache=cache, source_file="s.pdf")
    assert result.cached is False and len(calls) == 1
    assert result.finding == CACHE_FINDING_EVIDENCE_DRIFT


def test_a_drifted_native_evidence_blob_is_a_miss_with_a_finding(cache):
    """The blob half of M6: one word changed inside the stored native
    evidence — its own sha no longer reproduces — is the same drift."""
    input_sha = content_sha256(PDF)
    settings_key = ocr_settings_key()
    cache.put_ocr(input_sha, settings_key, _doc_with_native_evidence())
    key = cache_key(STAGE_OCR, input_sha, settings_key)
    path = cache._artifact_path(STAGE_OCR, key)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["artifact"]["document"]["native_evidence"]["pages"][0]["words"][0]["x0"] = 73.0
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = cached_ocr(PDF, compute=lambda: _doc(pages=["fresh", "fresh"]), cache=cache, source_file="s.pdf")
    assert result.cached is False and result.finding == CACHE_FINDING_EVIDENCE_DRIFT


def test_a_native_evidence_sha_stored_without_its_blob_is_a_drift(cache):
    input_sha = content_sha256(PDF)
    settings_key = ocr_settings_key()
    cache.put(STAGE_OCR, input_sha, settings_key, {"document": {
        "model": "native-pdf-text", "pages": ["a"], "page_integrity": [], "page_extractor": [],
        "evidence": None, "native_evidence": None, "native_evidence_sha256": "A" * 64,
    }})
    result = cached_ocr(PDF, compute=lambda: _doc(pages=["fresh"]), cache=cache, source_file="s.pdf")
    assert result.cached is False and result.finding == CACHE_FINDING_EVIDENCE_DRIFT


def test_a_schema_2_record_restores_with_no_native_evidence_and_still_analyses(cache):
    """CASE 13's last clause: a record written before schema 3 (no
    `native_evidence*` keys at all — every archive entry before this cell)
    restores with `native_evidence=None`, is a HIT (never a drift), and the
    restored document analyses through the real pipeline without crashing —
    the pipeline's own deterministic refusal on a synthetic page is the
    expected, documented answer, not an exception from the restore."""
    from analysis.pipeline import analyze_document

    input_sha = content_sha256(PDF)
    settings_key = ocr_settings_key()
    cache.put(STAGE_OCR, input_sha, settings_key, {"document": {
        "model": "native-pdf-text", "pages": ["Synthetic statement text with no issuer marker 2054"],
        "page_integrity": [], "page_extractor": ["native-pdf-text"], "evidence": None,
    }})

    def compute():
        pytest.fail("a schema-2 record is a valid hit; it must never be recomputed")

    result = cached_ocr(PDF, compute=compute, cache=cache, source_file="s.pdf")
    assert result.cached is True and result.finding is None
    doc = result.value
    assert doc.native_evidence is None and doc.native_evidence_sha256 is None
    markdown = doc.to_markdown()
    try:
        analyze_document(markdown, parse_mode="deterministic", sheets=doc.pages)
    except RuntimeError as refusal:
        assert "no deterministic parser matched" in str(refusal)


def test_native_evidence_round_trips_through_a_process_restart(data_dir):
    cache = ArtifactCache(Storage(data_dir))
    doc = _doc_with_native_evidence()
    cached_ocr(PDF, compute=lambda: doc, cache=cache, source_file="s.pdf")
    reopened = _reopen(data_dir)
    result = cached_ocr(PDF, compute=lambda: pytest.fail("must hit"), cache=reopened, source_file="s.pdf")
    assert result.cached is True
    assert result.value.native_evidence_sha256 == doc.native_evidence_sha256


# --- D6: the geometry-aware analysis key (case 12) -------------------------


def test_analysis_input_sha_without_evidence_is_byte_identical_to_the_phase_2_1_composition():
    """The deliberate deviation from the card's literal, pinned: a TEXT-ONLY
    call hashes exactly the two-field composition every run of record before
    this cell wrote (reproduced here from the legacy formula), so
    `tools/cohort_replay.py` and the telemetry observer keep resolving
    historical analysis artifacts by this function with no version
    parameter. The evidence field exists ONLY when a sha is supplied."""
    from analysis.parser_registry import admissible_text

    markdown = StatementMarkdown(source_file="s.pdf", model="m", pages=["one", "two"]).to_markdown()
    pages = ["one", "two"]
    legacy = text_sha256(json.dumps(
        {"text": text_sha256(admissible_text(markdown)), "sheets": sheets_sha256(pages)},
        sort_keys=True, separators=(",", ":"),
    ))
    assert analysis_input_sha(markdown, pages) == legacy
    assert analysis_input_sha(markdown, pages, evidence_sha256=None) == legacy
    assert analysis_input_sha(markdown, None) == text_sha256(json.dumps(
        {"text": text_sha256(admissible_text(markdown)), "sheets": None}, sort_keys=True, separators=(",", ":")))


def test_two_analyses_of_identical_markdown_with_and_without_evidence_take_different_keys(cache):
    """CASE 12 (M7): the same markdown and page partition, once text-only and
    once fed geometry built from an evidence with this sha — different input
    hashes, different cache entries; the same sha again is a hit; a different
    evidence sha is yet another entry."""
    markdown = StatementMarkdown(source_file="s.pdf", model="m", pages=["one", "two"]).to_markdown()
    pages = ["one", "two"]
    sha_a = "A" * 64
    sha_b = "B" * 64
    assert analysis_input_sha(markdown, pages) != analysis_input_sha(markdown, pages, evidence_sha256=sha_a)
    assert analysis_input_sha(markdown, pages, evidence_sha256=sha_a) != analysis_input_sha(markdown, pages, evidence_sha256=sha_b)
    assert analysis_input_sha(markdown, pages, evidence_sha256=sha_a.lower()) == analysis_input_sha(markdown, pages, evidence_sha256=sha_a)

    calls = []

    def compute():
        calls.append(1)
        return {"n": len(calls)}

    text_only = cached_analysis(markdown, compute=compute, cache=cache, parse_mode="deterministic",
                                analysis_settings=_AnalysisSettings(), sheets=pages)
    with_geometry = cached_analysis(markdown, compute=compute, cache=cache, parse_mode="deterministic",
                                    analysis_settings=_AnalysisSettings(), sheets=pages, evidence_sha256=sha_a)
    again = cached_analysis(markdown, compute=compute, cache=cache, parse_mode="deterministic",
                            analysis_settings=_AnalysisSettings(), sheets=pages, evidence_sha256=sha_a)
    other = cached_analysis(markdown, compute=compute, cache=cache, parse_mode="deterministic",
                            analysis_settings=_AnalysisSettings(), sheets=pages, evidence_sha256=sha_b)
    assert (text_only.cached, with_geometry.cached, again.cached, other.cached) == (False, False, True, False)
    assert text_only.cache_key != with_geometry.cache_key != other.cache_key
    assert len(calls) == 3


@pytest.mark.parametrize("bad", ["", "not-a-sha", "A" * 63, "G" * 64])
def test_a_malformed_evidence_sha_is_refused_never_hashed(bad):
    markdown = StatementMarkdown(source_file="s.pdf", model="m", pages=["one"]).to_markdown()
    with pytest.raises(ValueError):
        analysis_input_sha(markdown, ["one"], evidence_sha256=bad)


def test_reconstruction_mode_partitions_the_analysis_settings_key():
    """CASE 12 (M8): `Settings.reconstruction_mode` is settings-key material;
    `off` (the default, the archive's whole history) and `research` /
    `production` never share an analysis entry, and `generic_structurer` is
    derived from the SAME settings object."""
    from analysis.config import Settings

    off = Settings(api_key="", model="gemini-3.5-flash-lite", escalation_model="gemini-3.5-flash")
    research = Settings(api_key="", model="gemini-3.5-flash-lite", escalation_model="gemini-3.5-flash",
                        reconstruction_mode="research")
    production = Settings(api_key="", model="gemini-3.5-flash-lite", escalation_model="gemini-3.5-flash",
                          reconstruction_mode="production")
    keys = {analysis_settings_key(parse_mode="deterministic", analysis_settings=s) for s in (off, research, production)}
    assert len(keys) == 3
    # a stand-in without the field reads as `off`
    assert analysis_settings_key(parse_mode="deterministic", analysis_settings=_AnalysisSettings()) == \
        analysis_settings_key(parse_mode="deterministic", analysis_settings=off)



def test_hosted_extraction_opt_in_partitions_the_analysis_settings_key(monkeypatch):
    """P22-FENCE review F3 (Ocean's composition item): a payload produced
    with the hosted-extraction opt-in literal in the environment must not be
    served to a process without it. The key reads the fence's own predicate
    (`analysis.pipeline.hosted_extraction_opted_in`), so the two cannot
    disagree about what "opted in" means."""
    from analysis.pipeline import HOSTED_EXTRACTION_OPT_IN_ENV, HOSTED_EXTRACTION_OPT_IN_LITERAL

    monkeypatch.delenv(HOSTED_EXTRACTION_OPT_IN_ENV, raising=False)
    without = analysis_settings_key(analysis_settings=_AnalysisSettings())
    monkeypatch.setenv(HOSTED_EXTRACTION_OPT_IN_ENV, HOSTED_EXTRACTION_OPT_IN_LITERAL)
    with_literal = analysis_settings_key(analysis_settings=_AnalysisSettings())
    assert with_literal != without
    # Any other value is NOT the opt-in: same key as absent (the fence's rule).
    monkeypatch.setenv(HOSTED_EXTRACTION_OPT_IN_ENV, "yes")
    assert analysis_settings_key(analysis_settings=_AnalysisSettings()) == without

def test_the_retired_environment_variable_does_not_touch_the_analysis_key(monkeypatch):
    """M10 at the key: `GENERIC_STRUCTURER_ENABLED` is inert."""
    monkeypatch.delenv("RECONSTRUCTION_MODE", raising=False)
    monkeypatch.delenv("GENERIC_STRUCTURER_ENABLED", raising=False)
    before = analysis_settings_key(parse_mode="deterministic")
    monkeypatch.setenv("GENERIC_STRUCTURER_ENABLED", "1")
    assert analysis_settings_key(parse_mode="deterministic") == before
    monkeypatch.setenv("RECONSTRUCTION_MODE", "research")
    assert analysis_settings_key(parse_mode="deterministic") != before


# --- D7: the research partition in the OCR key (case 17, key half) ---------


def test_an_empty_research_partition_leaves_the_production_ocr_key_byte_identical():
    """The production key is unchanged when the field is empty: the material
    carries no `research_partition` at all (not an empty string)."""
    base = ocr_settings_key(ocr_settings=_OcrSettings())
    assert ocr_settings_key(ocr_settings=_OcrSettings(), research_partition="") == base
    assert ocr_settings_key(ocr_settings=_OcrSettings(), research_partition=None) == base


def test_a_non_empty_research_partition_is_its_own_ocr_partition():
    """M12: a research partition id is key material for EVERY extractor
    label; two ids are two partitions; production is a third."""
    base = ocr_settings_key(ocr_settings=_OcrSettings())
    alpha = ocr_settings_key(ocr_settings=_OcrSettings(), research_partition="p23-wave-a")
    beta = ocr_settings_key(ocr_settings=_OcrSettings(), research_partition="p23-wave-b")
    assert len({base, alpha, beta}) == 3
    visual_base = ocr_settings_key(ocr_settings=_OcrSettings(), force_ocr=True, allow_visual_ocr=True)
    visual_alpha = ocr_settings_key(ocr_settings=_OcrSettings(), force_ocr=True, allow_visual_ocr=True,
                                    research_partition="p23-wave-a")
    assert visual_base != visual_alpha != alpha


@pytest.mark.parametrize("bad", ["with space", "a/b", "-leading", "x" * 65, "tab\t", "nl\n"])
def test_a_research_partition_outside_the_closed_shape_is_refused(bad):
    with pytest.raises(ValueError):
        ocr_settings_key(ocr_settings=_OcrSettings(), research_partition=bad)
    with pytest.raises(TypeError):
        ocr_settings_key(ocr_settings=_OcrSettings(), research_partition=123)  # type: ignore[arg-type]


def test_cached_ocr_threads_the_research_partition_into_its_own_entry(cache):
    calls = []

    def compute():
        calls.append(1)
        return _doc(pages=[f"read {len(calls)}"])

    production = cached_ocr(PDF, compute=compute, cache=cache, allow_visual_ocr=False)
    research = cached_ocr(PDF, compute=compute, cache=cache, allow_visual_ocr=False, research_partition="p23-a")
    research_again = cached_ocr(PDF, compute=compute, cache=cache, allow_visual_ocr=False, research_partition="p23-a")
    assert (production.cached, research.cached, research_again.cached) == (False, False, True)
    assert production.cache_key != research.cache_key
    assert research_again.value.pages == ["read 2"] and len(calls) == 2

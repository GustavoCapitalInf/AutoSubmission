"""An evaluation server authorizes exact PDF bytes, including cache hits."""
from dataclasses import replace

import pytest

from ocr.visual_pair_config import (
    CUSTOMER_DATA_OPT_IN_ENV, CUSTOMER_DATA_OPT_IN_LITERAL,
    CUSTOMER_DOCUMENT_ALLOWLIST_ENV, VisualPairAuthorizationError,
    VisualPairConfigError, VisualPairSettings, check_remote_authorization, load_visual_pair_settings,
)
from vlm.receipts import sha256_bytes


def authorized_env(*hashes):
    return {CUSTOMER_DATA_OPT_IN_ENV: CUSTOMER_DATA_OPT_IN_LITERAL,
            CUSTOMER_DOCUMENT_ALLOWLIST_ENV: ",".join(hashes)}


def test_scoped_authorization_requires_exact_document_and_both_opt_ins():
    digest = sha256_bytes(b"%PDF synthetic approved")
    env = authorized_env(digest)
    settings = load_visual_pair_settings(env)
    check_remote_authorization(settings, environ=env, pdf_sha256=digest)
    for other in (None, sha256_bytes(b"%PDF synthetic changed")):
        with pytest.raises(VisualPairAuthorizationError, match="document_not_authorized"):
            check_remote_authorization(settings, environ=env, pdf_sha256=other)
    with pytest.raises(VisualPairAuthorizationError, match="remote_customer_data_refused"):
        check_remote_authorization(settings, environ={}, pdf_sha256=digest)
    with pytest.raises(VisualPairAuthorizationError, match="remote_customer_data_refused"):
        check_remote_authorization(replace(settings, customer_data_opt_in=False), environ=env,
                                   pdf_sha256=digest)


@pytest.mark.parametrize("value", ["", "not-a-hash", "A" * 64, "a" * 63, "a" * 64 + ",", "a" * 64 + "," + "a" * 64])
def test_malformed_allowlist_is_never_interpreted_as_unrestricted(value):
    with pytest.raises(VisualPairConfigError, match="allowlist is invalid"):
        load_visual_pair_settings({CUSTOMER_DOCUMENT_ALLOWLIST_ENV: value})


def test_runtime_narrowing_and_stale_settings_both_remain_effective():
    first, second = "a" * 64, "b" * 64
    broad = load_visual_pair_settings(authorized_env(first, second))
    narrow = load_visual_pair_settings(authorized_env(first))
    with pytest.raises(VisualPairAuthorizationError):
        check_remote_authorization(broad, environ=authorized_env(first), pdf_sha256=second)
    with pytest.raises(VisualPairAuthorizationError):
        check_remote_authorization(narrow, environ=authorized_env(first, second), pdf_sha256=second)
    with pytest.raises(VisualPairAuthorizationError):
        check_remote_authorization(narrow, environ={CUSTOMER_DATA_OPT_IN_ENV: CUSTOMER_DATA_OPT_IN_LITERAL},
                                   pdf_sha256=second)
    with pytest.raises(VisualPairAuthorizationError):
        check_remote_authorization(narrow, environ=authorized_env(first, "invalid"), pdf_sha256=first)


def test_document_scope_does_not_change_extraction_configuration():
    from ocr.visual_pair_config import visual_pair_settings_key_material

    first = load_visual_pair_settings(authorized_env("a" * 64))
    second = load_visual_pair_settings(authorized_env("b" * 64))
    assert visual_pair_settings_key_material(first) == visual_pair_settings_key_material(second)


# --- moved from tests/test_visual_pair_worker.py (model-code removal, slice S1) -------------------------------------
# The webapp worker no longer reads with the visual pair, so that file went with its subject. These pin
# ocr/visual_pair_config.py's own fences and webapp/artifact_cache.py's pair partition, which stay until the visual
# pair itself leaves (slice S4): the pair's command-line tools still reach them.


def test_customer_authorization_defaults_closed_even_for_loopback():
    settings = load_visual_pair_settings({})
    assert settings.execution_class == "remote_paid"
    assert settings.review_policy == "always_review"
    with pytest.raises(VisualPairAuthorizationError, match="remote_customer_data_refused"):
        check_remote_authorization(settings, environ={})
    check_remote_authorization(settings, data_scope="synthetic", environ={})


def test_customer_opt_in_requires_both_settings_and_current_environment():
    env = {CUSTOMER_DATA_OPT_IN_ENV: CUSTOMER_DATA_OPT_IN_LITERAL}
    authorized = load_visual_pair_settings(env)
    check_remote_authorization(authorized, environ=env)
    with pytest.raises(VisualPairAuthorizationError):
        check_remote_authorization(authorized, environ={})
    with pytest.raises(VisualPairAuthorizationError):
        check_remote_authorization(VisualPairSettings(), environ=env)
    with pytest.raises(VisualPairAuthorizationError):
        check_remote_authorization(authorized, data_scope="uploaded-synthetic", environ=env)


@pytest.mark.parametrize("changes", [
    {"proposer_revision": "main"}, {"reviewer_revision": "main"},
    {"proposer_url": "https://remote.invalid/v1"},
    {"reviewer_url": "http://127.0.0.1:18022/v1?token=secret"},
    {"execution_class": "loopback"}, {"execution_class": "local_free"}, {"review_policy": "auto"},
])
def test_pins_and_closed_configuration(changes):
    with pytest.raises(VisualPairConfigError):
        VisualPairSettings(**changes)


def test_pair_cache_is_partitioned_and_restores_review_evidence(monkeypatch, tmp_path):
    from ocr.config import load_settings
    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import cached_ocr, ocr_settings_key
    from webapp.jobs import JobStore
    from webapp.storage import Storage

    monkeypatch.setattr("vlm.pair.visual_pair_manifest", lambda: {"synthetic_contract": 1})
    settings = load_settings()
    original = ocr_settings_key(ocr_settings=settings)
    assert original == ocr_settings_key(ocr_settings=replace(settings, allow_visual_pair=True))
    pair_key = ocr_settings_key(allow_visual_pair=True, ocr_settings=settings)
    assert pair_key != original
    monkeypatch.setattr("vlm.pair.visual_pair_manifest", lambda: {"synthetic_contract": 2})
    assert pair_key != ocr_settings_key(allow_visual_pair=True, ocr_settings=settings)
    store = JobStore(Storage(tmp_path / "data"))
    evidence = {"version": 1, "gate": {"admitted": False, "reasons": ["no_rows"]}, "confidence": {"counts": {}}}
    doc = StatementMarkdown("synthetic.pdf", "visual-pair-dots-qwen", ["synthetic"], visual_pair=evidence)
    flags = dict(cache=store.cache, source_file="synthetic.pdf", force_ocr=True,
                 allow_visual_ocr=False, allow_visual_pair=True)
    first = cached_ocr(b"synthetic", compute=lambda: doc, **flags)
    second = cached_ocr(b"synthetic", compute=lambda: pytest.fail("re-read cached input"), **flags)
    assert not first.cached and second.cached
    assert second.value.visual_pair == evidence

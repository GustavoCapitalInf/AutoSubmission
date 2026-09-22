"""An evaluation server authorizes exact PDF bytes, including cache hits."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from ocr.visual_pair_config import (
    CUSTOMER_DATA_OPT_IN_ENV, CUSTOMER_DATA_OPT_IN_LITERAL,
    CUSTOMER_DOCUMENT_ALLOWLIST_ENV, VisualPairAuthorizationError,
    VisualPairConfigError, check_remote_authorization, load_visual_pair_settings,
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


def test_worker_checks_actual_pdf_bytes_before_cache(monkeypatch, tmp_path):
    from webapp.jobs import JobStore
    from webapp.storage import Storage
    from webapp.worker import _read_visual_pair

    digest = sha256_bytes(b"%PDF fabricated approved")
    for name, value in authorized_env(digest).items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr("webapp.worker._cached_ocr_timed",
                        lambda *a, **k: pytest.fail("unauthorized cache lookup"))
    store = JobStore(Storage(tmp_path / "data"))
    job = store.create("synthetic.pdf")
    with pytest.raises(VisualPairAuthorizationError, match="document_not_authorized"):
        _read_visual_pair(job.id, store, store.cache, b"%PDF fabricated changed", "synthetic.pdf",
                          SimpleNamespace(content_sha256=digest), timer=None)


def test_authorized_exact_document_can_restore_cached_pair_despite_uppercase_storage_hash(monkeypatch, tmp_path):
    from ocr.document import StatementMarkdown
    from ocr.inspect import content_sha256
    from webapp.artifact_cache import cached_ocr
    from webapp.jobs import JobStore
    from webapp.storage import Storage
    from webapp.worker import _read_visual_pair

    raw = b"%PDF fabricated exact approved cache"
    digest = sha256_bytes(raw)
    assert content_sha256(raw) == digest.upper() and digest != digest.upper()
    for name, value in authorized_env(digest).items():
        monkeypatch.setenv(name, value)
    settings = load_visual_pair_settings()
    store = JobStore(Storage(tmp_path / "data"))
    job = store.create("synthetic.pdf")
    evidence = {"version": 1, "gate": {"admitted": False, "reasons": ["no_rows"]}}
    document = StatementMarkdown("synthetic.pdf", "visual-pair-dots-qwen", ["FABRICATED HELD READING"],
                                 visual_pair=evidence)
    seeded = cached_ocr(raw, compute=lambda: document, cache=store.cache, source_file="synthetic.pdf",
                        content_hash=content_sha256(raw), force_ocr=True, allow_local_ocr=False,
                        allow_visual_ocr=False, allow_visual_pair=True, visual_pair_settings=settings)
    assert not seeded.cached
    monkeypatch.setattr("vlm.pair.extract_visual_pair", lambda *a, **k: pytest.fail("cached input re-extracted"))
    restored = _read_visual_pair(job.id, store, store.cache, raw, "synthetic.pdf",
                                SimpleNamespace(content_sha256=content_sha256(raw)), timer=None)
    assert restored.pages == document.pages and restored.visual_pair == evidence


def test_document_scope_does_not_change_extraction_configuration():
    from ocr.visual_pair_config import visual_pair_settings_key_material

    first = load_visual_pair_settings(authorized_env("a" * 64))
    second = load_visual_pair_settings(authorized_env("b" * 64))
    assert visual_pair_settings_key_material(first) == visual_pair_settings_key_material(second)

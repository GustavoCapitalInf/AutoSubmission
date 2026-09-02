"""Phase 2.1 cell 0: the Paddle configuration contract (`ocr/paddle_config.py`).

CASE 17 (missing `PADDLE_VAST_*` / provider / class -> fail closed, naming the
variable, no default host), the D2 declaration vocabulary and pairing, the
two opt-in gates of CASE 13 and CASE 20 at the configuration layer, the
loopback-only worker URL, the pins' shape, and the guarantee that no
instance-specific value (host, port, user, URL, token) ever reaches the
settings-key material or the masked display. No network, no model import.
"""
from __future__ import annotations

import json

import pytest

from ocr.config import RESERVED_MODEL_PREFIXES, validate_model_token
from ocr.paddle_config import (
    DATA_SCOPE_CUSTOMER,
    DATA_SCOPE_SYNTHETIC,
    EXECUTION_CLASSES,
    PADDLE_CUSTOMER_DATA_OPT_IN_ENV,
    PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL,
    PADDLE_DEFAULT_TUNNEL_LOCAL_PORT,
    PADDLE_DEFAULT_WORKER_PORT,
    PADDLE_EXTRACTOR_ID,
    PADDLE_MODEL_TOKEN,
    PADDLE_OCR_VERSION,
    PADDLE_PIPELINE_SWITCHES,
    PADDLE_REMOTE_OPT_IN_ENV,
    PADDLE_REMOTE_OPT_IN_LITERAL,
    PADDLE_TEXT_DETECTION_MODEL,
    PADDLE_TEXT_RECOGNITION_MODEL,
    PADDLEOCR_VERSION,
    PROVIDERS,
    PROVIDER_CLASS,
    REFUSAL_REASONS,
    PaddleConfigError,
    PaddleRefused,
    check_remote_authorization,
    load_paddle_settings,
    paddle_runtime_identity,
    paddle_settings_key_material,
)

#: Placeholder connection values for the tests — obviously not a real host.
VAST_ENV = {
    "PADDLE_PROVIDER": "vast.ai",
    "PADDLE_EXECUTION_CLASS": "remote_paid",
    "PADDLE_VAST_HOST": "example-host.invalid",
    "PADDLE_VAST_SSH_PORT": "22022",
    "PADDLE_VAST_SSH_USER": "someone",
}
LOCAL_ENV = {"PADDLE_PROVIDER": "local", "PADDLE_EXECUTION_CLASS": "local_free"}


# ---------------------------------------------------------------------------
# CASE 17: fail closed on missing configuration, naming the variable
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("missing", ["PADDLE_PROVIDER", "PADDLE_EXECUTION_CLASS", "PADDLE_VAST_HOST",
                                     "PADDLE_VAST_SSH_PORT", "PADDLE_VAST_SSH_USER"])
def test_a_missing_required_variable_is_named_and_nothing_is_defaulted(missing):
    env = {k: v for k, v in VAST_ENV.items() if k != missing}
    with pytest.raises(PaddleConfigError) as excinfo:
        load_paddle_settings(env)
    assert missing in str(excinfo.value)
    # The refusal never leaks any OTHER value either.
    assert "example-host.invalid" not in str(excinfo.value)


def test_an_empty_string_counts_as_missing():
    env = dict(VAST_ENV, PADDLE_VAST_HOST="")
    with pytest.raises(PaddleConfigError) as excinfo:
        load_paddle_settings(env)
    assert "PADDLE_VAST_HOST" in str(excinfo.value)


def test_an_empty_environment_is_refused_on_the_provider_first():
    with pytest.raises(PaddleConfigError) as excinfo:
        load_paddle_settings({})
    assert "PADDLE_PROVIDER" in str(excinfo.value)


def test_local_provider_needs_no_vast_variables():
    settings = load_paddle_settings(LOCAL_ENV)
    assert settings.provider == "local" and settings.execution_class == "local_free"
    assert settings.vast_host is None and settings.vast_ssh_port is None and settings.vast_ssh_user is None
    assert not settings.is_remote


# ---------------------------------------------------------------------------
# D2: closed vocabularies and the only legal pairings
# ---------------------------------------------------------------------------

def test_vocabularies_are_closed_and_paired():
    assert PROVIDERS == ("vast.ai", "local")
    assert EXECUTION_CLASSES == ("remote_paid", "local_free")
    assert dict(PROVIDER_CLASS) == {"vast.ai": "remote_paid", "local": "local_free"}


@pytest.mark.parametrize("provider,klass", [
    ("vast.ai", "local_free"),      # a Vast GPU called local
    ("local", "remote_paid"),       # a local worker called paid
    ("runpod", "remote_paid"),      # unknown provider
    ("vast.ai", "cloud"),           # unknown class
    ("VAST.AI", "remote_paid"),     # case is not normalised
])
def test_an_illegal_pairing_or_unknown_member_is_refused(provider, klass):
    env = dict(VAST_ENV, PADDLE_PROVIDER=provider, PADDLE_EXECUTION_CLASS=klass)
    with pytest.raises(PaddleConfigError):
        load_paddle_settings(env)


def test_localhost_in_the_worker_url_does_not_make_the_class_local():
    """CASE 16 at the configuration layer: the URL is loopback (the tunnel),
    the declaration says Vast — the declaration wins, and the settings are
    remote_paid."""
    settings = load_paddle_settings(dict(VAST_ENV, PADDLE_WORKER_URL="http://127.0.0.1:18765"))
    assert settings.worker_url == "http://127.0.0.1:18765"
    assert settings.provider == "vast.ai" and settings.execution_class == "remote_paid"
    assert settings.is_remote


# ---------------------------------------------------------------------------
# Ports, URL, token, runtime dir
# ---------------------------------------------------------------------------

def test_defaults_derive_a_loopback_worker_url_from_the_tunnel_port():
    settings = load_paddle_settings(VAST_ENV)
    assert settings.worker_port == PADDLE_DEFAULT_WORKER_PORT == 8765
    assert settings.tunnel_local_port == PADDLE_DEFAULT_TUNNEL_LOCAL_PORT == 18765
    assert settings.worker_url == "http://127.0.0.1:18765"
    assert settings.vast_ssh_port == 22022
    assert settings.worker_token is None
    assert settings.runtime_dir == ".paddle_runtime"


@pytest.mark.parametrize("url", [
    "http://0.0.0.0:8765", "http://192.168.1.5:8765", "http://example.com/ocr",
    "http://169.254.169.254/", "ftp://127.0.0.1/", "not a url", "http://100.64.0.1:8765",
])
def test_a_non_loopback_worker_url_is_refused(url):
    with pytest.raises(PaddleConfigError) as excinfo:
        load_paddle_settings(dict(VAST_ENV, PADDLE_WORKER_URL=url))
    assert "loopback" in str(excinfo.value)


@pytest.mark.parametrize("name,value", [
    ("PADDLE_VAST_SSH_PORT", "abc"), ("PADDLE_VAST_SSH_PORT", "0"), ("PADDLE_VAST_SSH_PORT", "70000"),
    ("PADDLE_WORKER_PORT", "-1"), ("PADDLE_TUNNEL_LOCAL_PORT", "http"),
])
def test_ports_must_be_integers_in_range(name, value):
    with pytest.raises(PaddleConfigError) as excinfo:
        load_paddle_settings(dict(VAST_ENV, **{name: value}))
    assert name in str(excinfo.value)


def test_whitespace_in_host_or_user_is_refused():
    with pytest.raises(PaddleConfigError):
        load_paddle_settings(dict(VAST_ENV, PADDLE_VAST_HOST="host name"))
    with pytest.raises(PaddleConfigError):
        load_paddle_settings(dict(VAST_ENV, PADDLE_VAST_SSH_USER="a b"))


# ---------------------------------------------------------------------------
# CASE 13 / CASE 20: the two opt-in gates, exact literals only
# ---------------------------------------------------------------------------

def test_remote_paid_without_the_exact_literal_is_refused():
    for value in (None, "1", "true", "yes", PADDLE_REMOTE_OPT_IN_LITERAL.lower(),
                  PADDLE_REMOTE_OPT_IN_LITERAL + "\n", "I_ACCEPT_REMOTE_PAID_OCR"):
        env = dict(VAST_ENV)
        if value is not None:
            env[PADDLE_REMOTE_OPT_IN_ENV] = value
        settings = load_paddle_settings(env)
        assert settings.remote_opt_in is False
        with pytest.raises(PaddleRefused) as excinfo:
            check_remote_authorization(settings, DATA_SCOPE_SYNTHETIC)
        assert excinfo.value.reason == "paddle_remote_opt_in_required"


def test_the_visual_rung_opt_in_does_not_authorize_paddle():
    """D3: one opt-in per paid extractor. `OCR_REMOTE_OPT_IN`'s literal set in
    the environment is invisible to Paddle."""
    env = dict(VAST_ENV, OCR_REMOTE_OPT_IN="I_ACCEPT_REMOTE_PAID_OCR")
    settings = load_paddle_settings(env)
    assert settings.remote_opt_in is False


def test_remote_paid_with_the_literal_permits_synthetic_scope_only():
    env = dict(VAST_ENV, **{PADDLE_REMOTE_OPT_IN_ENV: PADDLE_REMOTE_OPT_IN_LITERAL})
    settings = load_paddle_settings(env)
    assert settings.remote_opt_in is True
    check_remote_authorization(settings, DATA_SCOPE_SYNTHETIC)  # permitted
    with pytest.raises(PaddleRefused) as excinfo:
        check_remote_authorization(settings, DATA_SCOPE_CUSTOMER)
    assert excinfo.value.reason == "remote_customer_data_refused"


def test_customer_scope_on_remote_needs_the_second_literal_exactly():
    env = dict(VAST_ENV, **{PADDLE_REMOTE_OPT_IN_ENV: PADDLE_REMOTE_OPT_IN_LITERAL,
                            PADDLE_CUSTOMER_DATA_OPT_IN_ENV: "yes"})
    settings = load_paddle_settings(env)
    assert settings.customer_data_opt_in is False
    with pytest.raises(PaddleRefused):
        check_remote_authorization(settings, DATA_SCOPE_CUSTOMER)
    env[PADDLE_CUSTOMER_DATA_OPT_IN_ENV] = PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL
    settings = load_paddle_settings(env)
    assert settings.customer_data_opt_in is True
    check_remote_authorization(settings, DATA_SCOPE_CUSTOMER)  # only with the ruling's literal


def test_the_customer_literal_alone_does_not_stand_in_for_the_remote_opt_in():
    env = dict(VAST_ENV, **{PADDLE_CUSTOMER_DATA_OPT_IN_ENV: PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL})
    settings = load_paddle_settings(env)
    with pytest.raises(PaddleRefused) as excinfo:
        check_remote_authorization(settings, DATA_SCOPE_CUSTOMER)
    assert excinfo.value.reason == "paddle_remote_opt_in_required"


def test_local_free_needs_no_literal_for_either_scope():
    settings = load_paddle_settings(LOCAL_ENV)
    check_remote_authorization(settings, DATA_SCOPE_SYNTHETIC)
    check_remote_authorization(settings, DATA_SCOPE_CUSTOMER)


def test_an_unknown_data_scope_is_refused_everywhere():
    for env in (LOCAL_ENV, dict(VAST_ENV, **{PADDLE_REMOTE_OPT_IN_ENV: PADDLE_REMOTE_OPT_IN_LITERAL})):
        settings = load_paddle_settings(env)
        for scope in ("", "production", "SYNTHETIC", None):
            with pytest.raises(PaddleRefused) as excinfo:
                check_remote_authorization(settings, scope)  # type: ignore[arg-type]
            assert excinfo.value.reason == "paddle_data_scope_unknown"


def test_refusal_reasons_are_a_closed_vocabulary():
    with pytest.raises(ValueError):
        PaddleRefused("something_new")
    assert "paddle_runtime_mismatch" in REFUSAL_REASONS
    assert "paddle_worker_unreachable" in REFUSAL_REASONS


# ---------------------------------------------------------------------------
# D5 pins and the identity token
# ---------------------------------------------------------------------------

def test_the_pins_are_the_proven_configuration():
    assert PADDLEOCR_VERSION == "3.7.0"
    assert PADDLE_OCR_VERSION == "PP-OCRv5"
    assert PADDLE_TEXT_DETECTION_MODEL == "PP-OCRv5_server_det"
    assert PADDLE_TEXT_RECOGNITION_MODEL == "en_PP-OCRv5_mobile_rec"
    assert dict(PADDLE_PIPELINE_SWITCHES) == {
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": False,
        "return_word_box": True,
        "text_rec_score_thresh": 0.0,
    }
    with pytest.raises(TypeError):
        PADDLE_PIPELINE_SWITCHES["return_word_box"] = False  # type: ignore[index]


def test_no_v6_anywhere_in_the_identity():
    identity = json.dumps(paddle_runtime_identity()).lower()
    assert "v6" not in identity and "ocrv5" in identity


def test_the_model_token_obeys_the_closed_charset_and_is_reserved():
    assert validate_model_token(PADDLE_MODEL_TOKEN, allow_reserved=True) == PADDLE_MODEL_TOKEN
    assert PADDLE_MODEL_TOKEN == "paddle-ocr+ppocrv5"
    assert PADDLE_EXTRACTOR_ID == "paddle-ocr"
    # Cell R wires the reservation; until it composes this documents the expectation
    # and passes either way, so the two cells cannot deadlock on one another.
    if PADDLE_MODEL_TOKEN in RESERVED_MODEL_PREFIXES:
        with pytest.raises(Exception):
            validate_model_token(PADDLE_MODEL_TOKEN, allow_reserved=False)


# ---------------------------------------------------------------------------
# Secrets never reach key material, provenance or the display form
# ---------------------------------------------------------------------------

def test_settings_key_material_carries_the_pins_and_class_but_never_the_connection():
    env = dict(VAST_ENV, PADDLE_WORKER_TOKEN="s3cr3t-token", PADDLE_WORKER_URL="http://127.0.0.1:19999")
    settings = load_paddle_settings(env)
    material = paddle_settings_key_material(settings)
    text = json.dumps(material, sort_keys=True)
    assert material["provider"] == "vast.ai" and material["execution_class"] == "remote_paid"
    assert material["paddleocr_version"] == "3.7.0" and material["worker_contract"] == 1
    assert material["model_token"] == PADDLE_MODEL_TOKEN
    for forbidden in ("example-host.invalid", "22022", "someone", "s3cr3t-token", "19999", "127.0.0.1"):
        assert forbidden not in text


def test_masked_display_never_shows_a_value():
    env = dict(VAST_ENV, PADDLE_WORKER_TOKEN="s3cr3t-token")
    masked = load_paddle_settings(env).masked()
    text = json.dumps(masked)
    for forbidden in ("example-host.invalid", "22022", "someone", "s3cr3t-token"):
        assert forbidden not in text
    assert masked["vast_host"] == "<set>" and masked["worker_token"] == "<set>"


def test_local_and_vast_partition_the_key_material():
    remote = paddle_settings_key_material(load_paddle_settings(VAST_ENV))
    local = paddle_settings_key_material(load_paddle_settings(LOCAL_ENV))
    assert remote != local
    assert {k for k in remote if remote[k] != local[k]} == {"provider", "execution_class"}

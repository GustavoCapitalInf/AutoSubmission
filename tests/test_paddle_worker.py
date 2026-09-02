"""Phase 2.1 cell P: `ocr/paddle_worker.py`, offline (no `paddleocr`
installed, none imported). Every bound and error token; loopback-only bind
refusal (M8); the body-size bound (M9); the request-validation pipeline up
to (but never including) the model call.
"""
from __future__ import annotations

import base64
import json
import threading

import pytest

import ocr.paddle_worker as worker

#: A minimal 1x1 PNG (transparent). Defined here rather than imported from
#: `tests/paddle_fake_worker.py` so this module has no dependency on
#: `ocr/paddle_client.py` (kept committable, and testable, standalone).
TINY_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _payload(**overrides) -> dict:
    base = {
        "contract": worker.WORKER_CONTRACT,
        "request_id": "req-1",
        "page_index": 0,
        "image_png_b64": base64.b64encode(TINY_PNG_BYTES).decode("ascii"),
    }
    base.update(overrides)
    return base


VAST_ENV = {"PADDLE_PROVIDER": "vast.ai", "PADDLE_EXECUTION_CLASS": "remote_paid"}
LOCAL_ENV = {"PADDLE_PROVIDER": "local", "PADDLE_EXECUTION_CLASS": "local_free"}


# ---------------------------------------------------------------------------
# Startup configuration: identity pairing, bind address, port
# ---------------------------------------------------------------------------

def test_resolve_identity_accepts_the_legal_pairings():
    assert worker.resolve_identity(VAST_ENV) == {"provider": "vast.ai", "execution_class": "remote_paid"}
    assert worker.resolve_identity(LOCAL_ENV) == {"provider": "local", "execution_class": "local_free"}


@pytest.mark.parametrize("env", [
    {"PADDLE_PROVIDER": "vast.ai", "PADDLE_EXECUTION_CLASS": "local_free"},
    {"PADDLE_PROVIDER": "local", "PADDLE_EXECUTION_CLASS": "remote_paid"},
    {"PADDLE_PROVIDER": "runpod", "PADDLE_EXECUTION_CLASS": "remote_paid"},
    {"PADDLE_PROVIDER": "vast.ai", "PADDLE_EXECUTION_CLASS": "cloud"},
    {},
])
def test_resolve_identity_refuses_an_illegal_or_missing_pairing(env):
    with pytest.raises(worker.WorkerConfigError):
        worker.resolve_identity(env)


def test_m8_bind_address_refuses_anything_but_loopback():
    assert worker.resolve_bind_address({}) == "127.0.0.1"
    for bad in ("0.0.0.0", "192.168.1.5", "::", "localhost"):
        with pytest.raises(worker.WorkerConfigError):
            worker.resolve_bind_address({"PADDLE_WORKER_BIND": bad})


def test_build_server_refuses_a_non_loopback_host_even_if_asked_directly():
    """A second, independent enforcement point below `resolve_bind_address`
    — `build_server` itself refuses, so a future caller cannot bypass the
    startup check by constructing the server directly."""
    with pytest.raises(worker.WorkerConfigError):
        worker.build_server("0.0.0.0", 0, {"provider": "local", "execution_class": "local_free"}, None)


def test_resolve_port_defaults_and_validates():
    assert worker.resolve_port({}) == worker.DEFAULT_WORKER_PORT == 8765
    assert worker.resolve_port({"PADDLE_WORKER_PORT": "9999"}) == 9999
    for bad in ("abc", "-1", "0", "70000"):
        with pytest.raises(worker.WorkerConfigError):
            worker.resolve_port({"PADDLE_WORKER_PORT": bad})


# ---------------------------------------------------------------------------
# Bounded JSON parsing
# ---------------------------------------------------------------------------

def test_json_depth_guard_refuses_before_parsing():
    nested = "[" * (worker.MAX_JSON_DEPTH + 5) + "]" * (worker.MAX_JSON_DEPTH + 5)
    with pytest.raises(worker.WorkerRefused) as excinfo:
        worker.parse_bounded_json(nested.encode("utf-8"))
    assert excinfo.value.token == "bad_json"


def test_json_depth_guard_ignores_braces_inside_strings():
    text = json.dumps({"contract": 1, "note": "{" * 50})
    payload = worker.parse_bounded_json(text.encode("utf-8"))
    assert payload["note"] == "{" * 50


def test_non_object_top_level_json_refused():
    with pytest.raises(worker.WorkerRefused) as excinfo:
        worker.parse_bounded_json(b"[1, 2, 3]")
    assert excinfo.value.token == "bad_json"


def test_invalid_utf8_refused():
    with pytest.raises(worker.WorkerRefused) as excinfo:
        worker.parse_bounded_json(b"\xff\xfe\x00")
    assert excinfo.value.token == "bad_json"


# ---------------------------------------------------------------------------
# /ocr request validation (up to, never including, the model call)
# ---------------------------------------------------------------------------

def test_contract_mismatch_refused():
    with pytest.raises(worker.WorkerRefused) as excinfo:
        worker.handle_ocr_request(_payload(contract=2), identity={}, token=None, auth_header=None)
    assert excinfo.value.token == "contract_mismatch"


@pytest.mark.parametrize("field,value", [("request_id", ""), ("request_id", 5),
                                         ("page_index", -1), ("page_index", "0"), ("page_index", True)])
def test_bad_request_shape_refused(field, value):
    with pytest.raises(worker.WorkerRefused) as excinfo:
        worker.handle_ocr_request(_payload(**{field: value}), identity={}, token=None, auth_header=None)
    assert excinfo.value.token == "bad_json"


def test_unauthorized_without_matching_bearer_token():
    with pytest.raises(worker.WorkerRefused) as excinfo:
        worker.handle_ocr_request(_payload(), identity={}, token="secret", auth_header=None)
    assert excinfo.value.token == "unauthorized"
    with pytest.raises(worker.WorkerRefused) as excinfo:
        worker.handle_ocr_request(_payload(), identity={}, token="secret", auth_header="Bearer wrong")
    assert excinfo.value.token == "unauthorized"


def test_m9_body_over_the_bound_is_refused():
    """A real HTTP round trip against `worker.build_server`: the
    `Content-Length` bound is enforced from the HEADER alone, before the
    (enormous, never-sent) body would be read — proven by a request that
    declares an over-the-bound length but sends only a handful of bytes and
    still gets `body_too_large` back promptly, never a hang waiting to read
    bytes that never arrive. The bound's absolute value is pinned too — a
    mutant that merely widens `MAX_BODY_BYTES` (e.g. to 40 MiB) must fail
    here, not just a mutant that removes the check."""
    import http.client

    assert worker.MAX_BODY_BYTES == 32 * 1024 * 1024
    identity = {"provider": "local", "execution_class": "local_free"}
    server = worker.build_server("127.0.0.1", 0, identity, None)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
        try:
            conn.putrequest("POST", "/ocr")
            oversized = worker.MAX_BODY_BYTES + 1
            conn.putheader("Content-Length", str(oversized))
            conn.endheaders()
            conn.send(b"{}")  # far short of the declared length; the server must not wait for the rest
            response = conn.getresponse()
            body = json.loads(response.read().decode("utf-8"))
            assert response.status == 413
            assert body == {"error": "body_too_large"}
        finally:
            conn.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5.0)


def test_bad_base64_refused():
    with pytest.raises(worker.WorkerRefused) as excinfo:
        worker.handle_ocr_request(_payload(image_png_b64="not-base64!!"), identity={}, token=None, auth_header=None)
    assert excinfo.value.token == "bad_base64"


def test_not_png_refused():
    junk = base64.b64encode(b"this is not a png file at all").decode("ascii")
    with pytest.raises(worker.WorkerRefused) as excinfo:
        worker.handle_ocr_request(_payload(image_png_b64=junk), identity={}, token=None, auth_header=None)
    assert excinfo.value.token == "not_png"


def test_image_too_large_by_side_length_refused(monkeypatch):
    from PIL import Image
    import io

    monkeypatch.setattr(worker, "MAX_IMAGE_SIDE_PX", 10)
    big = Image.new("RGB", (20, 20), color="white")
    buffer = io.BytesIO()
    big.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    with pytest.raises(worker.WorkerRefused) as excinfo:
        worker.handle_ocr_request(_payload(image_png_b64=encoded), identity={}, token=None, auth_header=None)
    assert excinfo.value.token == "image_too_large"


def test_valid_shape_reaches_the_model_boundary_without_paddleocr_installed():
    """The request passes every bound and only fails once it reaches
    `_MODEL.infer`, which imports `paddleocr` — proving the whole validation
    pipeline runs with no such import anywhere above it."""
    with pytest.raises(worker.WorkerRefused) as excinfo:
        worker.handle_ocr_request(_payload(), identity={"provider": "local", "execution_class": "local_free"},
                                   token=None, auth_header=None)
    assert excinfo.value.token == "inference_failed"


def test_error_tokens_are_closed():
    with pytest.raises(ValueError):
        worker.WorkerRefused("something_new", 400)
    assert set(worker.ERROR_TOKENS) >= {
        "bad_json", "contract_mismatch", "body_too_large", "not_png", "image_too_large",
        "bad_base64", "unauthorized", "inference_failed",
    }


def test_version_payload_never_reveals_a_host_or_port():
    payload = worker.version_payload({"provider": "local", "execution_class": "local_free"})
    text = json.dumps(payload)
    for forbidden in ("127.0.0.1", "8765", "ssh"):
        assert forbidden not in text
    assert payload["paddleocr_version"] == worker.PADDLEOCR_VERSION_PIN == "3.7.0"
    assert payload["pipeline_switches"]["return_word_box"] is True


def test_module_is_importable_without_paddleocr():
    """This test module's own successful collection already proves it, but
    make the intent explicit: `paddleocr` must not be a name bound at
    `ocr.paddle_worker` module scope."""
    assert "paddleocr" not in worker.__dict__

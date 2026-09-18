import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from vlm import client as vclient


class _Fake(BaseHTTPRequestHandler):
    calls: list[dict] = []
    mode = "ok"

    def log_message(self, *args):  # silence
        pass

    def do_GET(self):
        if self.path == "/v1/models":
            body = json.dumps({"data": [{"id": "fake-model"}]}).encode()
        elif self.path == "/health":
            body = b'{"status":"ok"}'
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        _Fake.calls.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": json.loads(raw)})
        if _Fake.mode == "redirect":
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:9/elsewhere")
            self.end_headers()
            return
        if self.path == "/v1/chat/completions":
            content = json.dumps({"page_role": "blank_or_other"}) if _Fake.mode == "ok" else "not json"
            body = json.dumps({"choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                               "usage": {"prompt_tokens": 12, "completion_tokens": 3}}).encode()
        else:
            body = json.dumps({"blocks": [], "timing": {"total_ms": 1.0}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def server():
    _Fake.calls = []
    _Fake.mode = "ok"
    httpd = HTTPServer(("127.0.0.1", 0), _Fake)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_non_loopback_refused():
    with pytest.raises(vclient.TransportError) as exc:
        vclient.VlmClient("http://10.0.0.5:8000")
    assert "not_loopback" in str(exc.value)


def test_models_and_chat_structured(server):
    c = vclient.VlmClient(server, token="tok")
    assert c.models() == ["fake-model"]
    result = c.chat("fake-model", "Extract", image_jpeg=b"\xff\xd8\xffJPEG", schema={"type": "object"}, seed=7)
    assert result.parsed == {"page_role": "blank_or_other"} and result.finish_reason == "stop"
    assert result.prompt_tokens == 12 and result.completion_tokens == 3 and result.total_ms >= 0
    call = _Fake.calls[-1]
    assert call["auth"] == "Bearer tok"
    body = call["body"]
    assert body["temperature"] == 0 and body["seed"] == 7 and body["max_tokens"] == 4096
    assert body["response_format"] == {"type": "json_schema", "json_schema": {"name": "page_proposal", "schema": {"type": "object"}}}
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    parts = body["messages"][0]["content"]
    assert parts[0]["type"] == "image_url" and parts[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert parts[1] == {"type": "text", "text": "Extract"}
    assert len(result.request_sha256) == 64 and len(result.response_sha256) == 64


def test_chat_text_without_schema_or_image(server):
    c = vclient.VlmClient(server)
    result = c.chat("fake-model", "Table Recognition:", disable_thinking=False)
    assert result.parsed is None and result.text == '{"page_role": "blank_or_other"}'
    body = _Fake.calls[-1]["body"]
    assert "response_format" not in body and "chat_template_kwargs" not in body
    assert body["messages"][0]["content"] == [{"type": "text", "text": "Table Recognition:"}]


def test_unparseable_json_is_reported_not_raised(server):
    _Fake.mode = "badjson"
    result = vclient.VlmClient(server).chat("fake-model", "x", schema={"type": "object"})
    assert result.parsed is None and result.parse_error == "json_invalid"


def test_redirect_refused(server):
    _Fake.mode = "redirect"
    with pytest.raises(vclient.TransportError) as exc:
        vclient.VlmClient(server).chat("fake-model", "x")
    assert "redirect_refused" in str(exc.value) or "http_302" in str(exc.value)


def test_stage_a_worker_client(server):
    w = vclient.StageAWorkerClient(server, token="t")
    assert w.health() == {"status": "ok"}
    out = w.parse_page(b"\xff\xd8\xff", request_id="abc.p0", page_index=0)
    assert out["blocks"] == [] and _Fake.calls[-1]["body"]["contract"] == 1
    assert _Fake.calls[-1]["body"]["image_jpeg_b64"] and _Fake.calls[-1]["body"]["page_index"] == 0


def test_connection_refused_becomes_transport_error():
    c = vclient.VlmClient("http://127.0.0.1:9", timeout=1.0)
    with pytest.raises(vclient.TransportError):
        c.models()


def test_http_error_code_keeps_a_keyword_class_and_context_length_numbers_only():
    from vlm.client import http_error_code

    body = (b"{\"error\": {\"message\": \"This model's maximum context length is 32768 tokens. However, you requested "
            b"34000 tokens (22000 in the messages, 12000 in the completion). SECRET ROW TEXT\"}}")
    code = http_error_code(400, body)
    assert code == "http_400:context_length:32768,34000,22000,12000"
    assert "SECRET" not in code
    assert http_error_code(400, b"{\"error\": \"Invalid image payload ACCOUNT 1234\"}") == "http_400:image"
    assert http_error_code(400, b"{\"error\": \"something else 9999\"}") == "http_400"
    assert http_error_code(500, b"") == "http_500"

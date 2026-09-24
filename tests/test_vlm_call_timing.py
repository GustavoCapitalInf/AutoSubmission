"""Proposed with qwen_call_timing.patch (fabricated data only): a model call's receipt says when the request was sent,
and a failed call's receipt says when it began and how long it ran; no request byte changes."""
import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from vlm import client as vclient


class _Fake(BaseHTTPRequestHandler):
    bodies: list = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        _Fake.bodies.append(raw)
        body = json.dumps({"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                           "usage": {"prompt_tokens": 12, "completion_tokens": 3}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def server():
    _Fake.bodies = []
    httpd = HTTPServer(("127.0.0.1", 0), _Fake)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_a_call_records_when_it_was_sent_and_its_request_bytes_do_not_change(server):
    before = datetime.now(timezone.utc)
    result = vclient.VlmClient(server).chat("fake-model", "fabricated prompt", schema={"type": "object"})
    after = datetime.now(timezone.utc)
    started = datetime.fromisoformat(result.started_utc)
    assert before.replace(microsecond=before.microsecond // 1000 * 1000) <= started <= after
    assert result.total_ms > 0
    # The request carries no time: the bytes the server saw are the bytes hashed for replays.
    assert _Fake.bodies[0] == result.request_bytes and b"started" not in result.request_bytes


def test_the_receipt_carries_the_start_time_and_an_old_recording_carries_none(tmp_path):
    from vlm.pair import _record_call
    base = dict(text="{}", parsed={}, parse_error=None, finish_reason="stop", prompt_tokens=1, completion_tokens=1,
                total_ms=5.0, request_sha256=vclient.sha256_bytes(b"q"), response_sha256=vclient.sha256_bytes(b"r"),
                content_sha256=vclient.sha256_bytes(b"{}"), request_bytes=b"q", response_bytes=b"r")
    new = vclient.ChatResult(**base, started_utc="2031-03-01T12:00:00.000+00:00")
    receipt = _record_call(tmp_path, new, "p", page=1, stage="reviewer", image_sha="0" * 64, manifest={},
                           purpose="candidate_batch", batch_index=1, batch_count=2)
    assert receipt["started_utc"] == "2031-03-01T12:00:00.000+00:00" and receipt["purpose"] == "candidate_batch"
    old = vclient.ChatResult(**base)   # a recording made before the field existed
    assert "started_utc" not in _record_call(tmp_path, old, "p", page=1, stage="reviewer", image_sha="0" * 64,
                                             manifest={})

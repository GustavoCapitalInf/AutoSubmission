import base64
import io

import pytest
from PIL import Image

from vlm import stage_a_worker as w


class FakeRes:
    def __init__(self, payload):
        self.json = payload


class FakePipeline:
    def __init__(self):
        self.calls = []

    def predict(self, input, **kwargs):
        self.calls.append(input.shape)
        return [FakeRes({"res": {"parsing_res_list": [
            {"block_label": "table", "block_bbox": [1, 2, 3, 4], "block_content": "<table></table>", "block_order": 0, "block_id": 0},
            {"block_label": "text", "block_bbox": [5, 6, 7, 8], "block_content": "hello", "block_order": 1, "block_id": 1}]}})]


def _jpeg(w_=40, h_=30):
    buf = io.BytesIO()
    Image.new("RGB", (w_, h_), (255, 255, 255)).save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def test_handle_parse_maps_blocks_and_timings():
    pipe = FakePipeline()
    out = w.handle_parse({"contract": 1, "request_id": "abc.p0", "page_index": 0, "image_jpeg_b64": _jpeg()},
                         pipeline=pipe, token="t", auth_header="Bearer t")
    assert out["blocks"] == [{"label": "table", "bbox": [1, 2, 3, 4], "content": "<table></table>", "order": 0},
                             {"label": "text", "bbox": [5, 6, 7, 8], "content": "hello", "order": 1}]
    assert out["request_id"] == "abc.p0" and out["page_index"] == 0 and out["timing"]["inference_ms"] >= 0
    assert pipe.calls == [(30, 40, 3)]


def test_bad_token_and_bad_contract_refused():
    with pytest.raises(w.WorkerRefused) as exc:
        w.handle_parse({"contract": 1, "request_id": "x", "page_index": 0, "image_jpeg_b64": _jpeg()},
                       pipeline=FakePipeline(), token="t", auth_header="Bearer wrong")
    assert exc.value.code == "unauthorized"
    with pytest.raises(w.WorkerRefused) as exc:
        w.handle_parse({"contract": 2, "request_id": "x", "page_index": 0, "image_jpeg_b64": _jpeg()},
                       pipeline=FakePipeline(), token=None, auth_header=None)
    assert exc.value.code == "contract_mismatch"


def test_image_bounds():
    with pytest.raises(w.WorkerRefused) as exc:
        w.decode_jpeg_bounded(base64.b64encode(b"not an image").decode())
    assert exc.value.code == "image_invalid"
    assert w.decode_jpeg_bounded(_jpeg()).shape == (30, 40, 3)


def test_parse_bounded_json_and_version():
    assert w.parse_bounded_json(b'{"a": 1}') == {"a": 1}
    with pytest.raises(w.WorkerRefused):
        w.parse_bounded_json(b"[1]")
    version = w.version_payload({"VLM_A_BACKEND": "vllm-server"}, versions={"paddleocr": "3.7.0", "paddlex": "3.7.2"})
    assert version["retention"] == "none" and version["backend"] == "vllm-server" and version["pipeline_version"] == "v1.6"

from PIL import Image
from ocr.config import Settings
from ocr.ocr_client import build_prompt, image_to_data_uri, ocr_page, strip_det_tags


def _img():
    return Image.new("RGB", (12, 8), (255, 255, 255))


def _settings():
    return Settings(base_url="http://x/v1", model="m", api_key="EMPTY", timeout=5,
                    retries=3, ngram_size=35, window_size=128)


def test_image_to_data_uri():
    uri = image_to_data_uri(_img())
    assert uri.startswith("data:image/png;base64,")
    assert len(uri) > len("data:image/png;base64,")


def test_build_prompt_starts_with_image_token():
    p = build_prompt()
    assert p.startswith("<image>")
    assert len(p) > len("<image>")


def test_strip_det_tags_removes_region_annotations():
    raw = "<|det|>title [20, 82, 283, 147]<|/det|>HELLO WORLD"
    assert strip_det_tags(raw) == "HELLO WORLD"


def test_strip_det_tags_handles_multiple_tags():
    raw = ("<|det|>header [1, 2, 3, 4]<|/det|>CHASE\n"
           "<|det|>text [5, 6, 7, 8]<|/det|>Account: 123")
    assert strip_det_tags(raw) == "CHASE\nAccount: 123"


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
        m = _M()
        m.message = _M()
        m.message.content = self.text
        r = _M()
        r.choices = [m]
        return r


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


def test_ocr_page_strips_det_tags_from_response():
    client = _FakeClient("<|det|>title [1, 2, 3, 4]<|/det|>HELLO WORLD 12345")
    out = ocr_page(_img(), settings=_settings(), client=client)
    assert out == "HELLO WORLD 12345"


def test_ocr_page_retries_then_succeeds():
    client = _FakeClient("ok", fail_times=2)
    out = ocr_page(_img(), settings=_settings(), client=client)
    assert out == "ok"
    assert len(client.chat.completions.calls) == 3

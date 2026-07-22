from PIL import Image
from ocr.config import Settings
from ocr.ocr_client import build_prompt, image_to_data_uri, ocr_page


def _img():
    return Image.new("RGB", (12, 8), (255, 255, 255))


def _settings():
    return Settings(base_url="http://x/v1", model="m", api_key="EMPTY", timeout=5, retries=3)


def test_image_to_data_uri():
    uri = image_to_data_uri(_img())
    assert uri.startswith("data:image/png;base64,")
    assert len(uri) > len("data:image/png;base64,")


def test_build_prompt_mentions_html_tables():
    p = build_prompt().lower()
    assert "html" in p and "table" in p


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


def test_ocr_page_sends_image_and_prompt_and_returns_text():
    client = _FakeClient("# Page markdown\n<table></table>")
    out = ocr_page(_img(), settings=_settings(), client=client)
    assert out == "# Page markdown\n<table></table>"
    sent = client.chat.completions.calls[0]
    assert sent["model"] == "m"
    content = sent["messages"][-1]["content"]
    kinds = {part["type"] for part in content}
    assert "image_url" in kinds and "text" in kinds
    img_part = next(p for p in content if p["type"] == "image_url")
    assert img_part["image_url"]["url"].startswith("data:image/png;base64,")


def test_ocr_page_retries_then_succeeds():
    client = _FakeClient("ok", fail_times=2)
    out = ocr_page(_img(), settings=_settings(), client=client)
    assert out == "ok"
    assert len(client.chat.completions.calls) == 3

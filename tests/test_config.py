from ocr.config import load_settings, Settings


def test_defaults(monkeypatch):
    for k in ("OCR_BASE_URL", "OCR_MODEL", "OCR_API_KEY", "OCR_TIMEOUT",
              "OCR_RETRIES", "OCR_NGRAM_SIZE", "OCR_WINDOW_SIZE"):
        monkeypatch.delenv(k, raising=False)
    s = load_settings()
    assert isinstance(s, Settings)
    assert s.base_url == "http://localhost:8000/v1"
    assert s.model == "baidu/Unlimited-OCR"
    assert s.api_key == "EMPTY"
    assert s.timeout == 120.0
    assert s.retries == 3
    assert s.ngram_size == 35
    assert s.window_size == 128


def test_env_and_override(monkeypatch):
    monkeypatch.setenv("OCR_BASE_URL", "https://pod-8000.proxy.runpod.net/v1")
    monkeypatch.setenv("OCR_API_KEY", "tok")
    monkeypatch.setenv("OCR_TIMEOUT", "45")
    monkeypatch.setenv("OCR_RETRIES", "5")
    monkeypatch.setenv("OCR_NGRAM_SIZE", "40")
    monkeypatch.setenv("OCR_WINDOW_SIZE", "1024")
    s = load_settings(model_override="some/other-model")
    assert s.base_url == "https://pod-8000.proxy.runpod.net/v1"
    assert s.api_key == "tok"
    assert s.timeout == 45.0
    assert s.retries == 5
    assert s.ngram_size == 40
    assert s.window_size == 1024
    assert s.model == "some/other-model"

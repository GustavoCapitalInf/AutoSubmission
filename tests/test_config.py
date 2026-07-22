from ocr.config import load_settings, Settings


def test_defaults(monkeypatch):
    for k in ("NANONETS_BASE_URL", "NANONETS_MODEL", "NANONETS_API_KEY",
              "NANONETS_TIMEOUT", "NANONETS_RETRIES"):
        monkeypatch.delenv(k, raising=False)
    s = load_settings()
    assert isinstance(s, Settings)
    assert s.base_url == "http://localhost:8000/v1"
    assert s.model == "nanonets/Nanonets-OCR2-1.5B-exp"
    assert s.api_key == "EMPTY"
    assert s.timeout == 120.0
    assert s.retries == 3


def test_env_and_override(monkeypatch):
    monkeypatch.setenv("NANONETS_BASE_URL", "https://pod-8000.proxy.runpod.net/v1")
    monkeypatch.setenv("NANONETS_API_KEY", "tok")
    monkeypatch.setenv("NANONETS_TIMEOUT", "45")
    monkeypatch.setenv("NANONETS_RETRIES", "5")
    s = load_settings(model_override="some/other-model")
    assert s.base_url == "https://pod-8000.proxy.runpod.net/v1"
    assert s.api_key == "tok"
    assert s.timeout == 45.0
    assert s.retries == 5
    assert s.model == "some/other-model"

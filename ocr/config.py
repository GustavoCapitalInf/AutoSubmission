from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass
class Settings:
    base_url: str
    model: str
    api_key: str
    timeout: float
    retries: int
    ngram_size: int
    window_size: int


def load_settings(model_override: str | None = None) -> Settings:
    return Settings(
        base_url=os.environ.get("OCR_BASE_URL", "http://localhost:8000/v1"),
        model=model_override or os.environ.get("OCR_MODEL", "baidu/Unlimited-OCR"),
        api_key=os.environ.get("OCR_API_KEY", "EMPTY"),
        timeout=float(os.environ.get("OCR_TIMEOUT", "120")),
        retries=int(os.environ.get("OCR_RETRIES", "3")),
        ngram_size=int(os.environ.get("OCR_NGRAM_SIZE", "35")),
        window_size=int(os.environ.get("OCR_WINDOW_SIZE", "128")),
    )

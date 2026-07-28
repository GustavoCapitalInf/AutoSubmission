from __future__ import annotations
import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


@dataclass
class Settings:
    base_url: str
    model: str
    api_key: str
    timeout: float
    retries: int
    ngram_size: int
    window_size: int
    max_workers: int


def load_settings(model_override: str | None = None) -> Settings:
    return Settings(
        base_url=os.environ.get("OCR_BASE_URL", "http://localhost:8000/v1"),
        model=model_override or os.environ.get("OCR_MODEL", "baidu/Unlimited-OCR"),
        api_key=os.environ.get("OCR_API_KEY", "EMPTY"),
        timeout=float(os.environ.get("OCR_TIMEOUT", "120")),
        retries=int(os.environ.get("OCR_RETRIES", "3")),
        ngram_size=int(os.environ.get("OCR_NGRAM_SIZE", "35")),
        window_size=int(os.environ.get("OCR_WINDOW_SIZE", "128")),
        # How many pages to OCR concurrently. Defaults to 1 (sequential) because
        # on a single 24GB GPU (3090) the model already saturates the GPU per
        # page — concurrent requests thrash the KV cache and run SLOWER. On a
        # larger GPU (A100/H100) with spare KV-cache headroom, vLLM batches the
        # requests and this gives a real 2-3x speedup on multi-page statements
        # without changing output; raise OCR_MAX_WORKERS there (e.g. 4).
        max_workers=int(os.environ.get("OCR_MAX_WORKERS", "1")),
    )

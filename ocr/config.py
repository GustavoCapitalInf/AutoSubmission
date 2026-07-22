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


def load_settings(model_override: str | None = None) -> Settings:
    return Settings(
        base_url=os.environ.get("NANONETS_BASE_URL", "http://localhost:8000/v1"),
        model=model_override or os.environ.get("NANONETS_MODEL", "nanonets/Nanonets-OCR2-1.5B-exp"),
        api_key=os.environ.get("NANONETS_API_KEY", "EMPTY"),
        timeout=float(os.environ.get("NANONETS_TIMEOUT", "120")),
        retries=int(os.environ.get("NANONETS_RETRIES", "3")),
    )

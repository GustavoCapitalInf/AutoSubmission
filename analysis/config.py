"""Settings for the Gemini-backed analysis layer. Reads a gitignored .env so the
API key never lives in tracked code."""
from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    api_key: str
    # Cheap/fast default for extraction. Its mistakes are caught by reconciliation,
    # so a statement that fails reconciliation is re-extracted with the stronger
    # (still cheap) escalation model — you pay flash-lite prices for the clean 90%.
    model: str
    escalation_model: str


def load_settings() -> Settings:
    return Settings(
        api_key=os.environ.get("GEMINI_API_KEY", ""),
        model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        escalation_model=os.environ.get("GEMINI_ESCALATION_MODEL", "gemini-3.5-flash"),
    )

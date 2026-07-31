"""Settings for the Gemini-backed analysis layer. Reads a gitignored .env so the
API key never lives in tracked code."""
from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv
from .revenue import normalize_withholding_denominator_mode

load_dotenv()


@dataclass
class Settings:
    api_key: str
    # Cheap/fast default for extraction. Its mistakes are caught by reconciliation,
    # so a statement that fails reconciliation is re-extracted with the stronger
    # (still cheap) escalation model — you pay flash-lite prices for the clean 90%.
    model: str
    escalation_model: str
    withholding_denominator_mode: str = "legacy_eligible_deposits"


def load_settings() -> Settings:
    denominator_mode = normalize_withholding_denominator_mode(
        os.environ.get(
            "WITHHOLDING_DENOMINATOR_MODE",
            "legacy_eligible_deposits",
        )
    )
    return Settings(
        api_key=os.environ.get("GEMINI_API_KEY", ""),
        model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        escalation_model=os.environ.get("GEMINI_ESCALATION_MODEL", "gemini-3.5-flash"),
        withholding_denominator_mode=denominator_mode,
    )

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
    # The hosted extraction model — the ONE hosted call `analysis/pipeline.py`
    # can make, and only behind the operator opt-in documented there (P22-FENCE).
    model: str
    # RETAINED, NOT READ (R9, P22-FENCE). The second extraction this model was
    # for — re-extracting a statement that failed reconciliation and keeping
    # whichever result reconciled — was removed from `analysis/pipeline.py`;
    # nothing under `analysis/` reads this field now. It stays because it is
    # analysis settings-key material (`webapp/artifact_cache.py`), so removing
    # it would silently repartition every analysis cache.
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

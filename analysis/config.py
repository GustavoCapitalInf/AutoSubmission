"""Settings for the Gemini-backed analysis layer. Reads a gitignored .env so the
API key never lives in tracked code."""
from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv
from .revenue import DEFAULT_WITHHOLDING_DENOMINATOR_MODE, normalize_withholding_denominator_mode

load_dotenv()

#: P22-IDENTITY (Phase 2.2, D6). The reconstruction mode is the ONE switch
#: that says whether the generic structurer / reconstruction rung may run on
#: the unclaimed branch and, later, in what capacity: `off` (the default and
#: the whole archive's history — the rung never runs), `research` (what
#: Phase 2.3 flips, in research partitions only), `production` (Phase 2.4+,
#: after its own gate). A CLOSED vocabulary: anything else refuses at load —
#: never a silent default, because this value partitions the analysis cache
#: (`webapp/artifact_cache.py::analysis_settings_key`) and decides
#: `analysis.structurer.structurer_enabled()`. It replaces the retired
#: `GENERIC_STRUCTURER_ENABLED` environment contract, which is now inert.
RECONSTRUCTION_MODE_ENV = "RECONSTRUCTION_MODE"
RECONSTRUCTION_MODES: tuple[str, ...] = ("off", "research", "production")
RECONSTRUCTION_MODE_DEFAULT = "off"


def normalize_reconstruction_mode(value: object) -> str:
    """`RECONSTRUCTION_MODE` as loaded: `None` or blank means the default
    (`off`, so a shell that exports an empty variable does not refuse);
    every other value must be one of `RECONSTRUCTION_MODES` verbatim
    (lower-case, no surrounding whitespace beyond what `strip` removes) or
    loading refuses with a `ValueError` naming the vocabulary — the
    offending text is not echoed."""
    text = "" if value is None else str(value).strip()
    if text == "":
        return RECONSTRUCTION_MODE_DEFAULT
    if text not in RECONSTRUCTION_MODES:
        raise ValueError(
            f"{RECONSTRUCTION_MODE_ENV} must be one of {'|'.join(RECONSTRUCTION_MODES)}; refused"
        )
    return text


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
    # Owner ruling 2026-10-02 (the underwriter's Q7; R2-OW14): True revenue by default; legacy and verified selectable.
    withholding_denominator_mode: str = DEFAULT_WITHHOLDING_DENOMINATOR_MODE
    # P22-IDENTITY (D6): see `RECONSTRUCTION_MODES`. Validated on construction
    # too, so a `Settings` built by hand cannot carry an out-of-vocabulary mode.
    reconstruction_mode: str = RECONSTRUCTION_MODE_DEFAULT

    def __post_init__(self) -> None:
        self.reconstruction_mode = normalize_reconstruction_mode(self.reconstruction_mode)


def load_settings() -> Settings:
    # R2-OW14 (Q7): an unset, empty or invalid WITHHOLDING_DENOMINATOR_MODE reads as the default, True revenue.
    denominator_mode = normalize_withholding_denominator_mode(
        os.environ.get("WITHHOLDING_DENOMINATOR_MODE"),
        default=DEFAULT_WITHHOLDING_DENOMINATOR_MODE,
    )
    return Settings(
        api_key=os.environ.get("GEMINI_API_KEY", ""),
        model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        escalation_model=os.environ.get("GEMINI_ESCALATION_MODEL", "gemini-3.5-flash"),
        withholding_denominator_mode=denominator_mode,
        reconstruction_mode=normalize_reconstruction_mode(
            os.environ.get(RECONSTRUCTION_MODE_ENV, RECONSTRUCTION_MODE_DEFAULT)
        ),
    )

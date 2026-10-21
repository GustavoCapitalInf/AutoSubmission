"""`ocr/config.py` after the visual OCR settings were removed (model-code removal, slice S2).

The visual OCR `Settings` / `load_settings` (and their OCR_* environment reads) left with the Unlimited-OCR client;
their two tests here (`test_defaults`, `test_env_and_override`) were deleted with their subject. What the module
keeps is the provenance-token content policy and its import-time `.env` load. The OCR cache key's frozen copy of the
old defaults is pinned in `tests/test_artifact_cache.py`.
"""
from __future__ import annotations

import ast
import inspect

import ocr.config as ocr_config


def test_the_visual_ocr_settings_are_gone():
    assert not hasattr(ocr_config, "Settings")
    assert not hasattr(ocr_config, "load_settings")


def test_the_import_time_dotenv_load_stays():
    tree = ast.parse(inspect.getsource(ocr_config))
    module_level_calls = [
        node for node in tree.body
        if isinstance(node, ast.If)
        for inner in ast.walk(node)
        if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name) and inner.func.id == "load_dotenv"
    ]
    assert module_level_calls, "ocr/config.py must still call load_dotenv() at import"


def test_the_reserved_paddle_and_pair_tokens_are_literal_pins():
    """The two tokens are literals in ocr/config.py since S2. Both are literal pins now: the visual pair's since
    slice S4 removed `ocr.visual_pair_config`, the Paddle token's since slice S5 removed `ocr.paddle_config`. Stored
    readings carry both, and telemetry's vocabularies still name them (`PADDLE_MODEL_TOKENS`,
    `VISUAL_PAIR_MODEL_TOKENS`), so a token claiming either reserved rung is still refused from the environment."""
    from telemetry.record import PADDLE_MODEL_TOKENS, VISUAL_PAIR_MODEL_TOKENS

    assert ocr_config.RESERVED_MODEL_PREFIXES == (
        "native-pdf-text",
        "local-tesseract-ocr",
        "deterministic-native-preflight",
        "paddle-ocr+ppocrv5",
        "visual-pair-dots-qwen",
    )
    assert PADDLE_MODEL_TOKENS == frozenset({"paddle-ocr+ppocrv5"})
    assert VISUAL_PAIR_MODEL_TOKENS == frozenset({"visual-pair-dots-qwen"})

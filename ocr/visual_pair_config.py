"""Pinned visual-pair configuration and remote customer-data fence.

URLs are loopback transports, not evidence of local execution: SSH tunnels to
rented GPUs are remote. Customer uploads require an explicit second opt-in.
No machine address, secret, or endpoint URL enters receipts or cache material.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit

MODEL_TOKEN = "visual-pair-dots-qwen"
EXTRACTOR_ID = "visual_pair"
PROPOSER_REPOSITORY = "rednote-hilab/dots.mocr"
PROPOSER_REVISION = "e539fbb52280393adc081b289ec597430a0f9031"
REVIEWER_REPOSITORY = "nvidia/Qwen3.8-27B-NVFP4"
REVIEWER_REVISION = "482ca0f3832238542f8f5295dde86b5f22711d80"
CUSTOMER_DATA_OPT_IN_ENV = "VISUAL_PAIR_REMOTE_CUSTOMER_DATA_OPT_IN"
CUSTOMER_DATA_OPT_IN_LITERAL = "I_AUTHORIZE_CUSTOMER_DOCUMENTS_TO_REMOTE_VISUAL_PAIR"
CUSTOMER_DOCUMENT_ALLOWLIST_ENV = "VISUAL_PAIR_CUSTOMER_DOCUMENT_SHA256_ALLOWLIST"
CONFIG_VERSION = 1


class VisualPairConfigError(ValueError):
    """Safe configuration failure; never contains a supplied value."""


class VisualPairAuthorizationError(RuntimeError):
    """Safe refusal before reading a cache or sending any image."""


@dataclass(frozen=True)
class VisualPairSettings:
    proposer_url: str = "http://127.0.0.1:18013/v1"
    reviewer_url: str = "http://127.0.0.1:18022/v1"
    proposer_model: str = "dotsmocr"
    reviewer_model: str = "qwen3.8-27b-nvfp4"
    proposer_revision: str = PROPOSER_REVISION
    reviewer_revision: str = REVIEWER_REVISION
    execution_class: str = "remote_paid"
    customer_data_opt_in: bool = False
    customer_document_allowlist: tuple[str, ...] | None = None
    timeout: float = 900
    max_tokens: int = 12000
    seed: int = 0
    temperature: float = 0
    render_long_edge: int = 1540
    review_policy: str = "always_review"

    def __post_init__(self) -> None:
        if self.customer_document_allowlist is not None:
            entries = self.customer_document_allowlist
            if (not isinstance(entries, tuple) or not entries
                    or any(not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
                           for value in entries)
                    or len(set(entries)) != len(entries)):
                raise VisualPairConfigError("visual pair customer document allowlist is invalid")
        for name in ("proposer_url", "reviewer_url"):
            try:
                endpoint = urlsplit(getattr(self, name))
                legal = (endpoint.scheme == "http" and endpoint.hostname in
                         {"127.0.0.1", "localhost", "::1"} and endpoint.port is not None
                         and not endpoint.username and not endpoint.password
                         and not endpoint.query and not endpoint.fragment)
            except ValueError:
                legal = False
            if not legal:
                raise VisualPairConfigError(f"{name} must be a loopback HTTP endpoint")
        if self.execution_class != "remote_paid":
            raise VisualPairConfigError("VISUAL_PAIR_EXECUTION_CLASS is invalid")
        if self.proposer_revision != PROPOSER_REVISION or self.reviewer_revision != REVIEWER_REVISION:
            raise VisualPairConfigError("visual pair model revisions must match the frozen pins")
        if self.proposer_model != "dotsmocr" or self.reviewer_model != "qwen3.8-27b-nvfp4":
            raise VisualPairConfigError("visual pair served model names must match the frozen pair")
        if self.review_policy not in {"always_review", "admit_gated"}:
            raise VisualPairConfigError("VISUAL_PAIR_REVIEW_POLICY is invalid")
        if self.temperature != 0 or self.seed != 0 or self.max_tokens != 12000:
            raise VisualPairConfigError("visual pair generation settings must match the frozen pins")
        if self.render_long_edge != 1540 or self.timeout <= 0:
            raise VisualPairConfigError("visual pair rendering or timeout settings are invalid")


def load_visual_pair_settings(environ: Mapping[str, str] | None = None) -> VisualPairSettings:
    env = os.environ if environ is None else environ
    try:
        timeout = float(env.get("VISUAL_PAIR_TIMEOUT", "900"))
    except ValueError as exc:
        raise VisualPairConfigError("VISUAL_PAIR_TIMEOUT must be numeric") from exc
    return VisualPairSettings(
        proposer_url=env.get("VISUAL_PAIR_PROPOSER_URL", "http://127.0.0.1:18013/v1"),
        reviewer_url=env.get("VISUAL_PAIR_REVIEWER_URL", "http://127.0.0.1:18022/v1"),
        execution_class=env.get("VISUAL_PAIR_EXECUTION_CLASS", "remote_paid"),
        customer_data_opt_in=env.get(CUSTOMER_DATA_OPT_IN_ENV) == CUSTOMER_DATA_OPT_IN_LITERAL,
        customer_document_allowlist=(tuple(value.strip() for value in env[CUSTOMER_DOCUMENT_ALLOWLIST_ENV].split(","))
                                     if CUSTOMER_DOCUMENT_ALLOWLIST_ENV in env else None),
        timeout=timeout,
        review_policy=env.get("VISUAL_PAIR_REVIEW_POLICY", "always_review"),
    )


def check_remote_authorization(
    settings: VisualPairSettings, *, data_scope: str = "customer",
    environ: Mapping[str, str] | None = None,
    pdf_sha256: str | None = None,
) -> None:
    if data_scope not in {"customer", "synthetic"}:
        raise VisualPairAuthorizationError("visual_pair_data_scope_unknown")
    # A synthetic caller is explicit and never selected by the upload worker.
    if data_scope == "synthetic":
        return
    env = os.environ if environ is None else environ
    if not (settings.customer_data_opt_in and
            env.get(CUSTOMER_DATA_OPT_IN_ENV) == CUSTOMER_DATA_OPT_IN_LITERAL):
        raise VisualPairAuthorizationError("visual_pair_remote_customer_data_refused")
    # Evaluation in the webapp can authorize particular documents without
    # opening the fence to every later upload. This is checked on cache hits too.
    # Check both the loaded settings and the current environment, so narrowing
    # a running process's authorization cannot be bypassed with stale settings.
    current = env.get(CUSTOMER_DOCUMENT_ALLOWLIST_ENV)
    lists = [settings.customer_document_allowlist]
    if current is not None:
        lists.append(tuple(value.strip() for value in current.split(",")))
    for allowed in lists:
        if allowed is not None and (not allowed or len(set(allowed)) != len(allowed)
                                    or any(re.fullmatch(r"[0-9a-f]{64}", value) is None for value in allowed)
                                    or not pdf_sha256 or pdf_sha256 not in allowed):
            raise VisualPairAuthorizationError("visual_pair_customer_document_not_authorized")


def visual_pair_settings_key_material(settings: VisualPairSettings) -> dict:
    from vlm.pair import visual_pair_manifest

    return {
        "config_version": CONFIG_VERSION,
        "model_token": MODEL_TOKEN,
        "proposer_repository": PROPOSER_REPOSITORY,
        "proposer_revision": settings.proposer_revision,
        "reviewer_repository": REVIEWER_REPOSITORY,
        "reviewer_revision": settings.reviewer_revision,
        "execution_class": settings.execution_class,
        "max_tokens": settings.max_tokens,
        "temperature": settings.temperature,
        "seed": settings.seed,
        "render_long_edge": settings.render_long_edge,
        "pipeline": visual_pair_manifest(),
    }

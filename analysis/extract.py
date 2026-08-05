"""Stage 1 — LLM extraction. Turn the OCR markdown into a normalized Statement
with Gemini's structured output (Pydantic response_schema → validated object).

The model only transcribes and normalizes; it never computes totals or averages.
All math happens later in deterministic Python (reconcile.py / metrics.py)."""
from __future__ import annotations
import re
import time
from dataclasses import dataclass
from typing import Callable
from google import genai
from google.genai import types
from .config import Settings, load_settings
from .schema import Statement

_client: genai.Client | None = None
_client_config: tuple[str, int, int] | None = None

# The OCR markdown embeds check-image crops as base64 <img> tags for the viewer.
# Gemini only needs the text ledger, and a single image-heavy statement can carry
# megabytes of base64 (Santander: 30 images, ~3 MB) — pure prompt bloat/cost and a
# context-blowout risk. Strip the tags before sending; the transactions are all in
# the text tables anyway.
_IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)


@dataclass(frozen=True)
class ExtractionAttempt:
    """Non-sensitive operational evidence for one external model call."""

    provider: str
    model: str
    source_kind: str
    status: str
    latency_ms: int
    prompt_tokens: int | None = None
    response_tokens: int | None = None
    thinking_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None
    pricing_version: str | None = None
    error_type: str | None = None


# Standard paid-tier rates published by Google on 2026-07-30. Keeping the
# version beside every estimate makes historical cost reports auditable when
# provider pricing changes. Unknown model IDs still report tokens but no cost.
_MODEL_RATES_PER_MILLION: dict[str, tuple[float, float]] = {
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.5-flash": (1.50, 9.00),
    "gemini-3.6-flash": (1.50, 7.50),
}
GEMINI_PRICING_VERSION = "google-gemini-paid-standard-2026-07-30"


def _model_rates(model: str) -> tuple[float, float] | None:
    if model in _MODEL_RATES_PER_MILLION:
        return _MODEL_RATES_PER_MILLION[model]
    for model_id, rates in _MODEL_RATES_PER_MILLION.items():
        if model.startswith(model_id + "-"):
            return rates
    return None


def estimate_extraction_cost(
    model: str,
    *,
    prompt_tokens: int | None,
    response_tokens: int | None,
) -> float | None:
    rates = _model_rates(model)
    if rates is None or prompt_tokens is None or response_tokens is None:
        return None
    input_rate, output_rate = rates
    cost = (prompt_tokens * input_rate + response_tokens * output_rate) / 1_000_000
    return round(cost, 8)


def _token_count(value: object, name: str) -> int | None:
    raw = getattr(value, name, None)
    return int(raw) if raw is not None else None


def strip_embedded_images(markdown: str) -> str:
    return _IMG_TAG_RE.sub("", markdown)


def _get_client(settings: Settings) -> genai.Client:
    global _client, _client_config
    config = (settings.api_key, settings.request_timeout_ms, settings.http_attempts)
    if _client is None or _client_config != config:
        if not settings.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set (put it in .env).")
        _client = genai.Client(
            api_key=settings.api_key,
            http_options=types.HttpOptions(
                timeout=settings.request_timeout_ms,
                retry_options=types.HttpRetryOptions(attempts=settings.http_attempts),
            ),
        )
        _client_config = config
    return _client


_INSTRUCTIONS = """\
You are extracting a bank statement into structured data for underwriting. Work
only from the text provided — do not invent, compute, or "fix" numbers.

Rules:
- Copy every amount exactly as printed (keep cents).
- `amount` is signed: NEGATIVE for money leaving the account (debits, withdrawals,
  checks, ACH payments, fees) and POSITIVE for money entering (deposits, credits).
- `direction` is "debit" for negative amounts and "credit" for positive amounts.
- `date`: output full ISO dates (YYYY-MM-DD). Statements often print MM/DD with no
  year — infer the year from the statement period (watch for a Dec->Jan rollover).
- `running_balance`: the balance printed after a row, if present; otherwise null.
- `source_page`: copy the one-based page number from the nearest "--- Page N ---"
  marker. This is evidence for audit, not a transaction date.
- Apply the same `source_page` rule to every row copied into
  `stated_daily_balances`.
- ACCOUNT ISOLATION: count the distinct financial accounts represented in the
  document and set `document_account_count`. Never merge activity, balances, or
  summaries from different accounts. For one account, set
  `account_selection_status="single_account"`. If several accounts are present
  and one clearly labeled operating/checking account can be isolated, extract
  only that account and set `account_selection_status="selected_primary"`. If a
  unique account cannot be isolated, set `account_selection_status="ambiguous"`,
  leave account-dependent values unset, and do not fabricate a combined ledger.
- Copy the printed account type and routing/transit number when present.
- Capture the bank's own printed SUMMARY block into the statement-level `stated_*`
  and beginning/ending balance fields. This is the most important part — on many
  statements (especially small banks) the per-transaction detail is incomplete but
  the summary is authoritative. Copy the bank's totals; never add them up yourself.
  Summary fields: beginning/ending balance, total deposits/credits, total
  checks/debits (positive), their counts, service charge, interest paid, days in
  period, and any printed average balance ("Average Ledger", "Average Collected",
  "Average Daily Balance").
  Only set `stated_nsf_count` if the statement explicitly prints a COUNT of NSF /
  returned / overdraft ITEMS for THIS period. Many statements instead show
  overdraft/returned-item FEES as dollar amounts, often in a "This Period /
  Year-to-Date" table — those are not counts; leave `stated_nsf_count` null. Never
  guess it from a dollar amount, a service charge, or a year-to-date figure.
- SUMMARY ALIGNMENT — read carefully. Small-bank statements often print the
  summary as a column of LABELS followed by a separate column of VALUES, e.g.:
      Previous Balance / 3 Deposits/Credits / 26 Checks/Debits / Service Charge /
      Interest Paid / Ending Balance   ...then...   78.68- / 7,329.22 / 3,945.12 /
      8.00 / .00 / 3,297.42
  Align them BY POSITION: the 1st value goes with the 1st label, etc. Do NOT read a
  count as an amount (e.g. "26 Checks/Debits" means count=26 with the amount on the
  values side — here 3,945.12). A trailing "-" means negative (78.68- = -78.68).
  Sanity check yourself: beginning + credits - debits - service_charge + interest
  should equal the ending balance. If it doesn't, you mis-aligned — fix it.
- A transaction is one real posting. List each once, in order. OCR often misplaces
  amounts: a debit's amount may be glued into its description with the Amount cell
  blank (e.g. "PREM PMT BCBS OF AL 32.00"); use that trailing value as the amount.
- Pages are separated by "--- Page N ---" markers; merge them into one statement.

Statement markdown follows:
"""


def extract_statement(
    markdown: str,
    *,
    settings: Settings | None = None,
    model: str | None = None,
    attempt_sink: Callable[[ExtractionAttempt], None] | None = None,
) -> Statement:
    """Extract one statement's markdown into a Statement object."""
    settings = settings or load_settings()
    client = _get_client(settings)
    selected_model = model or settings.model
    started = time.perf_counter()
    try:
        resp = client.models.generate_content(
            model=selected_model,
            contents=_INSTRUCTIONS + strip_embedded_images(markdown),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=Statement,
            ),
        )
        stmt = resp.parsed
        if not isinstance(stmt, Statement):  # schema violation / empty response
            raise RuntimeError(f"extraction did not return a Statement: {resp.text[:300]!r}")

        if attempt_sink is not None:
            usage = getattr(resp, "usage_metadata", None)
            prompt_tokens = _token_count(usage, "prompt_token_count") if usage else None
            candidate_tokens = _token_count(usage, "candidates_token_count") if usage else None
            thinking_tokens = _token_count(usage, "thoughts_token_count") if usage else None
            response_tokens = None
            if candidate_tokens is not None or thinking_tokens is not None:
                response_tokens = (candidate_tokens or 0) + (thinking_tokens or 0)
            attempt_sink(
                ExtractionAttempt(
                    provider="google_gemini",
                    model=selected_model,
                    source_kind="ocr_markdown",
                    status="success",
                    latency_ms=round((time.perf_counter() - started) * 1000),
                    prompt_tokens=prompt_tokens,
                    response_tokens=response_tokens,
                    thinking_tokens=thinking_tokens,
                    total_tokens=_token_count(usage, "total_token_count") if usage else None,
                    estimated_cost_usd=estimate_extraction_cost(
                        selected_model,
                        prompt_tokens=prompt_tokens,
                        response_tokens=response_tokens,
                    ),
                    pricing_version=GEMINI_PRICING_VERSION,
                )
            )
        return stmt
    except Exception as exc:
        if attempt_sink is not None:
            attempt_sink(
                ExtractionAttempt(
                    provider="google_gemini",
                    model=selected_model,
                    source_kind="ocr_markdown",
                    status="error",
                    latency_ms=round((time.perf_counter() - started) * 1000),
                    pricing_version=GEMINI_PRICING_VERSION,
                    error_type=type(exc).__name__,
                )
            )
        raise

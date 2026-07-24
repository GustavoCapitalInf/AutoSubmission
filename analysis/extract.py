"""Stage 1 — LLM extraction. Turn the OCR markdown into a normalized Statement
with Gemini's structured output (Pydantic response_schema → validated object).

The model only transcribes and normalizes; it never computes totals or averages.
All math happens later in deterministic Python (reconcile.py / metrics.py)."""
from __future__ import annotations
from google import genai
from google.genai import types
from .config import Settings, load_settings
from .schema import Statement

_client: genai.Client | None = None


def _get_client(settings: Settings) -> genai.Client:
    global _client
    if _client is None:
        if not settings.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set (put it in .env).")
        _client = genai.Client(api_key=settings.api_key)
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
- Include summary-line amounts (beginning/ending balance) at the statement level,
  not as transactions. List each real transaction once, in statement order.
- Also capture the bank's own printed SUMMARY block into the statement-level
  `stated_*` fields: total deposits/credits, total checks/debits (as a positive
  number), their counts, days in period, and any printed average balance
  ("Average Ledger", "Average Collected", "Average Daily Balance"). These are the
  bank's totals — copy them; do not add them up yourself.
- OCR often misplaces amounts: a debit's amount may be glued into its description
  text with the Amount column left blank (e.g. "PREM PMT BCBS OF AL 32.00"). When
  a row's amount cell is empty but a monetary value appears at the end of its
  description, use that trailing value as the transaction amount.
- Pages are separated by "--- Page N ---" markers; merge them into one statement.

Statement markdown follows:
"""


def extract_statement(markdown: str, *, settings: Settings | None = None,
                      model: str | None = None) -> Statement:
    """Extract one statement's markdown into a Statement object."""
    settings = settings or load_settings()
    client = _get_client(settings)
    resp = client.models.generate_content(
        model=model or settings.model,
        contents=_INSTRUCTIONS + markdown,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Statement,
            temperature=0.0,
        ),
    )
    stmt = resp.parsed
    if not isinstance(stmt, Statement):  # schema violation / empty response
        raise RuntimeError(f"extraction did not return a Statement: {resp.text[:300]!r}")
    return stmt

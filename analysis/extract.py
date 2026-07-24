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

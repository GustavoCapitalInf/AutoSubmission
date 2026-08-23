"""Stage 1 — LLM extraction. Turn the OCR markdown into a normalized Statement
with Gemini's structured output (Pydantic response_schema → validated object).

The model only transcribes and normalizes; it never computes totals or averages.
All math happens later in deterministic Python (reconcile.py / metrics.py).

A REFUSAL IN THIS MODULE NEVER QUOTES THE RESPONSE (W3 §EXTRACTPRIV, extending
§MG-C2 D1 and §MONEYPRIV from the printed cell to the model's transcription of
it). Both raises here are built from a closed vocabulary, and
`tests/test_extraction_refusal_is_private.py` reads this file's AST so that a
future one has to be too."""
from __future__ import annotations
import re
from google import genai
from google.genai import types
from .config import Settings, load_settings
from .schema import Statement

_client: genai.Client | None = None

# The OCR markdown embeds check-image crops as base64 <img> tags for the viewer.
# Gemini only needs the text ledger, and a single image-heavy statement can carry
# megabytes of base64 (Santander: 30 images, ~3 MB) — pure prompt bloat/cost and a
# context-blowout risk. Strip the tags before sending; the transactions are all in
# the text tables anyway.
_IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)


def strip_embedded_images(markdown: str) -> str:
    return _IMG_TAG_RE.sub("", markdown)


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
  summary as a column of LABELS followed by a separate column of VALUES. The
  shape, with <V1>…<V6> standing for whatever money tokens the page prints and
  <N> for a printed count:
      Previous Balance / <N> Deposits/Credits / <N> Checks/Debits / Service Charge /
      Interest Paid / Ending Balance   ...then...   <V1>- / <V2> / <V3> /
      <V4> / <V5> / <V6>
  Align them BY POSITION: the 1st value goes with the 1st label, etc. Do NOT read a
  count as an amount ("<N> Checks/Debits" means count=<N>, with that section's
  amount on the values side — <V3> here). A trailing "-" means the value is
  negative (<V1>- is minus <V1>).
  Sanity check yourself: beginning + credits - debits - service_charge + interest
  should equal the ending balance. If it doesn't, you mis-aligned — fix it.
- A transaction is one real posting. List each once, in order. OCR often misplaces
  amounts: a debit's amount may be glued onto the END of its description with the
  Amount cell left blank ("<description as printed> <money token>"); use that
  trailing value as the amount.
- Pages are separated by "--- Page N ---" markers; merge them into one statement.

Statement markdown follows:
"""


# ---------------------------------------------------------------------------
# THE REFUSAL VOCABULARY (W3 §EXTRACTPRIV)
#
# When the model returns something that is not a `Statement`, this module has
# to say so — and until batch 6 it said so by quoting the model back at the
# operator: `RuntimeError(f"...: {resp.text[:300]!r}")`. Those 300 characters
# are the model's TRANSCRIPTION of the statement: the account number, the
# balances, the payees, in the order the bank printed them. They travelled.
# This is the LLM branch, the one branch `analyze_markdown` makes no totality
# promise for (`analysis/pipeline.py` :686 calls `extract_statement` unguarded),
# so the exception leaves the pipeline intact and every consumer publishes the
# message: `webapp/worker.py` :94 returns `str(e)` as the job's
# `analysis_error`, which `webapp/storage.py` writes into the durable store and
# `webapp/app.py` serves back on three routes; `batch.py` :267 and
# `coverage_audit.py` :193 write `f"{type(e).__name__}: {e}"` into a CSV cell;
# `analyze.py` catches nothing at all and lets it render as a traceback.
#
# The refusal still has to be DIAGNOSABLE — "did the model get cut off, or was
# it blocked, or did it answer with prose?" is the whole question at 3am — so
# it names why, from a vocabulary fixed before the document existed:
#
#   * `stop_reason`, a NAME from the SDK's own `FinishReason` enum. Anything
#     not in that enum is reported as `unknown` rather than echoed, because an
#     unrecognised value is precisely the case where we cannot prove it carries
#     no document text.
#   * `response`, three-valued: `empty` / `nonempty` / `unavailable`. A boolean
#     about the body, not a measurement of it.
#
# No length, and that is a decision rather than an omission. A character count
# would be the natural third field and it is *nearly* content-free — but it is
# derived from the document, it puts a digit run in a message whose whole
# defence is that it has none, and it costs the property that makes this
# provable: the set of messages this module can emit is FINITE and enumerable
# without reading a statement. `test_the_message_set_is_finite_and_enumerable`
# writes that set out and asserts the raise never leaves it.
# ---------------------------------------------------------------------------

#: The SDK's finish-reason names, read off the enum rather than typed out: the
#: vocabulary belongs to `google.genai`, so a version that adds a member should
#: widen this by upgrading the SDK and never by this file drifting behind it.
_STOP_REASONS = frozenset(member.name for member in types.FinishReason)

#: The same names, as a lookup that RETURNS OUR OWN copy of the string.
#:
#: `x in _STOP_REASONS` is a question answered by the candidate's `__hash__`
#: and `__eq__`, and a `str` subclass may answer it however it likes while its
#: actual characters — and its `__format__` — say something else entirely. A
#: membership test therefore licenses the VALUE, never the OBJECT: `_stop_reason`
#: looks the matched name up here and returns what this module put in, so the
#: only strings that can reach the message are the ones built from the enum at
#: import time. Unreachable from the SDK, which mints real enum members; one
#: dict and one subscript to make that a property rather than a dependency.
_CANONICAL_STOP_REASON = {name: name for name in _STOP_REASONS}

#: What an unreadable finish reason is called. Fail-closed: it is what a
#: missing candidate, a `None`, a value from a newer API and an attribute
#: access that raises all collapse to.
_UNKNOWN_STOP_REASON = "unknown"

#: The three response states. `unavailable` is not a synonym for `empty` — it
#: means the body could not be inspected at all, which is a different fact and
#: a different bug hunt.
_RESPONSE_STATES = ("empty", "nonempty", "unavailable")

_REFUSAL = "extraction did not return a Statement (stop_reason={}, response={})"


def _stop_reason(response: types.GenerateContentResponse) -> str:
    """The first candidate's finish reason, as a name from the SDK's enum.

    Every failure mode returns `unknown`, including the ones that are not
    supposed to happen: no candidates, a `finish_reason` of `None`, a value the
    installed SDK has no member for, or an attribute access that raises because
    the object is not the shape we think. A diagnosis that says `unknown` costs
    a debugging session; a diagnosis that echoes whatever it found costs the
    property this module is defending.

    The matched name is never itself returned — see `_CANONICAL_STOP_REASON`.
    Passing the membership test earns the VALUE, not a place in the message.
    """
    try:
        candidates = response.candidates or ()
        reason = candidates[0].finish_reason if candidates else None
        name = getattr(reason, "name", reason)
        if isinstance(name, str) and name in _STOP_REASONS:
            return _CANONICAL_STOP_REASON[name]
    except Exception:                     # noqa: BLE001 — see the docstring
        return _UNKNOWN_STOP_REASON
    return _UNKNOWN_STOP_REASON


def _response_state(response: types.GenerateContentResponse) -> str:
    """Is there a body at all: `empty` / `nonempty` / `unavailable`.

    The body is deliberately never bound to a name here. `response.text` is
    read inside the truth test and discarded, so the transcription is not a
    local of any frame this module contributes — and because `_extraction_refusal`
    RETURNS the exception, none of these frames is in the raised traceback
    either.
    """
    try:
        return "nonempty" if response.text else "empty"
    except Exception:                     # noqa: BLE001 — see `_stop_reason`
        return "unavailable"


def _extraction_refusal(response: types.GenerateContentResponse) -> RuntimeError:
    """THE refusal for the LLM branch. Returns the exception; never raises.

    Returning rather than raising is load-bearing, for the reason §MONEYPRIV
    established at the money grammar: the call site writes
    ``raise _extraction_refusal(resp)`` from outside any ``except``, so the
    exception carries neither a ``__cause__`` nor a ``__context__`` for a
    traceback renderer to walk. It also keeps these helper frames — the ones
    holding `response` — out of the raised traceback entirely.

    `response` is passed in only to be MEASURED: it reaches the message through
    nothing but a name from `_STOP_REASONS` and one of `_RESPONSE_STATES`.
    """
    return RuntimeError(_REFUSAL.format(_stop_reason(response), _response_state(response)))


def extract_statement(markdown: str, *, settings: Settings | None = None,
                      model: str | None = None) -> Statement:
    """Extract one statement's markdown into a Statement object."""
    settings = settings or load_settings()
    client = _get_client(settings)
    resp = client.models.generate_content(
        model=model or settings.model,
        contents=_INSTRUCTIONS + strip_embedded_images(markdown),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Statement,
            temperature=0.0,
        ),
    )
    stmt = resp.parsed
    if not isinstance(stmt, Statement):  # schema violation / empty response
        # The message names the refusal, never the transcription — §EXTRACTPRIV
        # above. This also restores the branch's own stated contract on the
        # "empty response" half of that comment: the old spelling subscripted
        # `resp.text`, which is `None` whenever the response has no text part
        # (a safety block, a blocked prompt, no candidates), so the diagnostic
        # died with `TypeError: 'NoneType' object is not subscriptable` and the
        # RuntimeError this branch documents was never constructed.
        raise _extraction_refusal(resp)
    # §CURRSRC. `Statement` is this call's `response_schema`, so `currency` is
    # not the only currency field the model can fill — `currency_source` is in
    # the schema too, and a model that returned `"printed"` would be certifying
    # its own provenance. It may not: whatever came back is DISCARDED here and
    # replaced by the one class that is true of this whole branch, which is
    # that a language model produced the denomination and the platform did not
    # verify the evidence. Unconditional, because the model's `"USD"` is not
    # distinguishable from the field default it may simply have echoed.
    stmt.currency_source = "model_extracted"
    return stmt

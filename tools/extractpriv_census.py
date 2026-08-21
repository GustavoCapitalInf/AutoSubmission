"""The LLM-branch refusal census (W3 §EXTRACTPRIV §XP5).

What does the refusal actually carry, per response shape? Prints the class, the
message, the cause/context chain and any leaked fragment for each of the seven
reachable shapes, so the before/after table in the log is re-derivable on any
tree rather than asserted.

    python -m tools.extractpriv_census

Makes NO hosted-model call and needs no API key: the responses are real
`google.genai.types.GenerateContentResponse` objects built locally and the
client is a stub. On the base tree it reports 4 of 7 shapes leaking; on this
one, 0.
"""
from __future__ import annotations

import re
import sys
import traceback

from google.genai import types

import analysis.extract as ex

WORD = "ACMEPAYROLL"
DIGITS = "4471009238"

POISON = (
    '{"bank": "ACMEPAYROLL BANK NA", "account_number": "4471009238", '
    '"beginning_balance": 118432.19, "transactions": [{"date": "2026-01-04", '
    '"description": "ACH DEBIT ACMEPAYROLL 4471009238", "amount": -12345.67, '
    '"running_balance": 106086.52}, {"date": "2026-01-07", "description": '
    '"DEPOSIT ACMEPAYROLL", "amount": 9876.54}]'
)


def _resp(*, text: str | None, finish_reason, parsed=None, candidates=True):
    parts = None if text is None else [types.Part(text=text)]
    cands = None
    if candidates:
        cands = [types.Candidate(
            content=types.Content(role="model", parts=parts),
            finish_reason=finish_reason,
        )]
    resp = types.GenerateContentResponse(candidates=cands)
    resp.parsed = parsed
    return resp


SHAPES = {
    "schema_violation_stop": _resp(text=POISON, finish_reason=types.FinishReason.STOP),
    "truncated_max_tokens": _resp(text=POISON[:180], finish_reason=types.FinishReason.MAX_TOKENS),
    "parsed_is_a_dict": _resp(text=POISON, finish_reason=types.FinishReason.STOP,
                              parsed={"bank": f"{WORD} BANK NA"}),
    "empty_no_parts": _resp(text=None, finish_reason=types.FinishReason.SAFETY),
    "empty_no_candidates": _resp(text=None, finish_reason=None, candidates=False),
    "prohibited_content": _resp(text=None, finish_reason=types.FinishReason.PROHIBITED_CONTENT,
                                candidates=True),
    "recitation_with_text": _resp(text=POISON, finish_reason=types.FinishReason.RECITATION),
}


class _Models:
    def __init__(self, resp):
        self._resp = resp

    def generate_content(self, **kwargs):
        return self._resp


class _Client:
    def __init__(self, resp):
        self.models = _Models(resp)


def _chain(exc):
    out, seen, cur = [], set(), exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        out.append(cur)
        cur = cur.__cause__ or cur.__context__
    return out


def _rendered(exc):
    parts = [str(link) for link in _chain(exc)]
    parts.append("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    return "\n".join(parts)


def main() -> int:
    leaks = 0
    for name, resp in SHAPES.items():
        ex._get_client = lambda settings, _r=resp: _Client(_r)  # type: ignore[assignment]
        settings = ex.Settings(api_key="not-a-key", model="stub", escalation_model="stub")
        try:
            ex.extract_statement("--- Page 1 ---\nstub markdown", settings=settings)
            print(f"{name}: NO EXCEPTION")
            continue
        except BaseException as exc:  # noqa: BLE001
            rendered = _rendered(exc)
            frags = [WORD, DIGITS, POISON, *re.findall(r"\d{3,}", POISON)]
            found = sorted({f for f in frags if f in rendered})
            chain = [type(link).__name__ for link in _chain(exc)]
            print(f"--- {name}")
            print(f"    class      : {type(exc).__name__}")
            print(f"    message    : {str(exc)!r}")
            print(f"    chain      : {chain}")
            print(f"    cause/ctx  : {type(exc.__cause__).__name__}/{type(exc.__context__).__name__}")
            print(f"    LEAKED     : {found[:6]}{' ...' if len(found) > 6 else ''}")
            if found:
                leaks += 1
    print(f"\nSHAPES={len(SHAPES)} LEAKING={leaks}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

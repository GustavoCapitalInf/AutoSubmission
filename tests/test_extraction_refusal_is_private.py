"""THE EXCEPTION BOUNDARY ON THE LLM BRANCH (W3 §EXTRACTPRIV).

`analysis/money.py` holds the printed cell; `analysis/extract.py` holds the
model's TRANSCRIPTION of it — the same statement, re-typed by Gemini, with the
account number and the balances in it. When the model returns something that is
not a `Statement`, this module used to refuse by quoting 300 characters of that
transcription into a `RuntimeError`:

    raise RuntimeError(f"extraction did not return a Statement: {resp.text[:300]!r}")

and that exception travels. Unlike the deterministic branch, whose every
`detect`/`parse` runs behind `parser_registry._guarded` (registry ids and class
names only) and whose repair stage is reduced to `type(exc).__name__`
(§PIPE5), the LLM branch at `analysis/pipeline.py` :686 calls
`extract_statement` UNGUARDED — `analyze_markdown` makes no totality promise
there — so the message reaches `webapp/worker.py` :94, which returns `str(e)`
as the job's `analysis_error` for `webapp/storage.py` to write into the durable
store and `webapp/app.py` to serve back. (Batch 6's §WORKER-PRIVACY withholds
it at that boundary; this file asserts the SOURCE-side property, which is the
one that holds for `batch.py`'s CSV cell, for `analyze.py`'s traceback, and for
a reader nobody has written yet. Neither closure is the other's excuse.)

WHAT THIS FILE ASSERTS, and why in this shape:

* it drives the real `extract_statement`, with a stub client and REAL
  `google.genai.types.GenerateContentResponse` objects built locally. No hosted
  model is called by any test here ($0 vendor; `test_no_client_is_ever_built`
  proves the module never even constructed one), and using the SDK's own types
  means `.text`, `.candidates` and `.parsed` behave exactly as they do in
  production rather than as a hand-written double imagines.
* it poisons the transcription with canaries that cannot occur in a legitimate
  refusal, then looks for them in three places — ``str(exc)``, the whole
  ``__cause__``/``__context__`` chain, and a rendered traceback. The chain
  matters because ``raise ... from exc`` passes a ``str()`` test and fails a
  traceback test.
* it asserts on digit RUNS, because the dangerous fragment of a leaked
  transcription is not the prose around it: it is the account number and the
  balance. The refusal vocabulary contains no digit at all, so the assertion
  can be made in its strongest form (`test_a_refusal_contains_no_digits`).
* `test_the_message_set_is_finite_and_enumerable` writes out every message the
  module can produce — `(FinishReason names + "unknown") x 3 response states` —
  and pins the raise inside it. That is the property a length field would have
  cost, and it is what makes "this message cannot contain the document" a
  statement about the code rather than about the inputs someone tried.
* the AST guards cover the branches no input reaches: a raise added on an
  unhit path, or the old f-string restored, fails there even if the dynamic
  sweep never runs it.
"""
from __future__ import annotations

import ast
import pathlib
import re
import traceback

import pytest
from google.genai import types

import analysis.extract as ex
from analysis.schema import Statement

# --- the poison -------------------------------------------------------------
#
# Two canaries, because a leaked transcription has two shapes. WORD is what the
# description column holds; DIGITS is account-shaped, which is the fragment
# that actually matters and the one a "the message is shorter now" fix would
# still leak.
WORD = "ACMEPAYROLL"
DIGITS = "4471009238"

#: A model response with the statement in it: the transcription the old message
#: quoted the first 300 characters of.
POISON = (
    '{"bank": "ACMEPAYROLL BANK NA", "account_number": "4471009238", '
    '"beginning_balance": 118432.19, "transactions": [{"date": "2026-01-04", '
    '"description": "ACH DEBIT ACMEPAYROLL 4471009238", "amount": -12345.67, '
    '"running_balance": 106086.52}, {"date": "2026-01-07", "description": '
    '"DEPOSIT ACMEPAYROLL", "amount": 9876.54}]'
)

#: The markdown handed to `extract_statement`. Poisoned too: the request side
#: is a leak surface of its own if a refusal ever starts quoting its input.
POISONED_MARKDOWN = f"--- Page 1 ---\n{WORD} BANK NA  acct {DIGITS}\nDEPOSIT 12,345.67"


def _response(*, text: str | None, finish_reason, parsed=None, candidates: bool = True):
    """A real `GenerateContentResponse`, built locally — never fetched."""
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


#: The refusal's reachable shapes, named for the failure they represent so a
#: leak says which one leaked. Each is a way `resp.parsed` ends up not being a
#: `Statement`, which is the branch under test.
SHAPES = {
    # prose or malformed JSON where a Statement was asked for
    "schema_violation_stop": dict(text=POISON, finish_reason=types.FinishReason.STOP),
    # the truncation case: a long statement runs the model out of output tokens
    "truncated_max_tokens": dict(text=POISON[:180], finish_reason=types.FinishReason.MAX_TOKENS),
    # the SDK parsed something, but not into our schema
    "parsed_is_a_dict": dict(text=POISON, finish_reason=types.FinishReason.STOP,
                             parsed={"bank": f"{WORD} BANK NA", "account_number": DIGITS}),
    # blocked: a candidate with no parts at all, so `resp.text` is None
    "empty_no_parts": dict(text=None, finish_reason=types.FinishReason.SAFETY),
    # blocked at the prompt: no candidates whatsoever
    "empty_no_candidates": dict(text=None, finish_reason=None, candidates=False),
    "prohibited_content": dict(text=None, finish_reason=types.FinishReason.PROHIBITED_CONTENT),
    "recitation_with_text": dict(text=POISON, finish_reason=types.FinishReason.RECITATION),
}


class _StubModels:
    def __init__(self, resp):
        self._resp = resp
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        return self._resp


class _StubClient:
    """Stands in for `genai.Client`. Nothing here reaches the network."""

    def __init__(self, resp):
        self.models = _StubModels(resp)


@pytest.fixture
def refuse(monkeypatch):
    """Run the real `extract_statement` against a fabricated response.

    Patches `_get_client`, not the module-level `_client`, so no client object
    is constructed and no API key is read — see `test_no_client_is_ever_built`.
    """
    def _run(shape: str):
        resp = _response(**SHAPES[shape])
        monkeypatch.setattr(ex, "_get_client", lambda settings: _StubClient(resp))
        settings = ex.Settings(api_key="", model="stub-model", escalation_model="stub-model")
        with pytest.raises(BaseException) as excinfo:      # noqa: PT011 — the class IS the assertion
            ex.extract_statement(POISONED_MARKDOWN, settings=settings)
        return excinfo.value

    return _run


def _chain(exc: BaseException) -> list[BaseException]:
    """The exception and everything reachable from it, cause or context.

    Walks BOTH links and ignores `__suppress_context__`: suppression only
    changes what the default renderer PRINTS, and the objects are still there
    for anything that walks them. The property this file wants is that the
    quoting exception does not exist, not that it is politely hidden.
    """
    out: list[BaseException] = []
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        out.append(cur)
        cur = cur.__cause__ or cur.__context__
    return out


def _rendered(exc: BaseException) -> str:
    """Everything a diagnostic surface could print about this exception."""
    parts = [str(link) for link in _chain(exc)]
    parts.append("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    return "\n".join(parts)


def _fragments() -> list[str]:
    """The pieces whose appearance anywhere in a refusal would be a leak."""
    return [WORD, DIGITS, POISON, POISON[:300], POISON[:180],
            *re.findall(r"\d{3,}", POISON), *re.findall(r"\d{3,}", POISONED_MARKDOWN)]


# --- the card ---------------------------------------------------------------

@pytest.mark.parametrize("shape", list(SHAPES))
def test_a_refusal_never_carries_the_transcription(shape, refuse):
    """THE CARD. Whatever the model returned, none of it may be in the refusal."""
    exc = refuse(shape)
    rendered = _rendered(exc)
    leaked = sorted({f for f in _fragments() if f in rendered})
    assert not leaked, f"{shape} leaked {leaked!r} into its refusal:\n{rendered}"


@pytest.mark.parametrize("shape", list(SHAPES))
def test_a_refusal_contains_no_digits(shape, refuse):
    """The vocabulary has no number in it, so this can be asserted absolutely.

    Stronger than "no run of three or more", and deliberately so: a response
    LENGTH is the field that would have gone here, and forgoing it buys an
    assertion no future edit can weaken by accident.
    """
    message = str(refuse(shape))
    assert not any(ch.isdigit() for ch in message), message


@pytest.mark.parametrize("shape", list(SHAPES))
def test_a_refusal_carries_no_chained_exception_at_all(shape, refuse):
    """The chain is severed, not suppressed.

    `_extraction_refusal` RETURNS the exception and the call site raises it from
    outside any handler, so both links are empty. A refusal raised from inside
    an `except` — or with `from exc` — would pass the `str(exc)` test above and
    leak the moment a traceback was rendered.
    """
    exc = refuse(shape)
    assert exc.__cause__ is None, f"{shape}: refusal carries a __cause__"
    assert exc.__context__ is None, f"{shape}: refusal carries a __context__"


@pytest.mark.parametrize("shape", list(SHAPES))
def test_the_refusal_stays_a_runtime_error(shape, refuse):
    """The CLASS is the contract. `analysis/pipeline.py` :705 reduces an
    escalation failure to `type(e).__name__`, `batch.py` and
    `coverage_audit.py` record the same, and `discovery/runner.py` files it as
    an `error_type` — so changing the class would change what those consumers
    publish even though none of them changes behaviour on it."""
    assert type(refuse(shape)) is RuntimeError


# --- the vocabulary, closed and enumerated ----------------------------------

def _every_possible_message() -> set[str]:
    """Every string `_extraction_refusal` can return, without reading a document."""
    return {
        ex._REFUSAL.format(reason, state)
        for reason in {*ex._STOP_REASONS, ex._UNKNOWN_STOP_REASON}
        for state in ex._RESPONSE_STATES
    }


@pytest.mark.parametrize("shape", list(SHAPES))
def test_the_message_set_is_finite_and_enumerable(shape, refuse):
    """The message the raise produced is a member of a set computed from the
    SDK's enum and three constants — no input involved."""
    assert str(refuse(shape)) in _every_possible_message()


def test_the_message_set_is_actually_small():
    """A sanity bound on the enumeration above: it is (reasons + 1) x 3, and
    every member is digit-free. If a future edit interpolates something
    unbounded, one of these two facts stops being true."""
    messages = _every_possible_message()
    assert len(messages) == (len(ex._STOP_REASONS) + 1) * len(ex._RESPONSE_STATES)
    assert ex._STOP_REASONS, "the SDK's FinishReason enum came back empty"
    assert not any(ch.isdigit() for m in messages for ch in m)


@pytest.mark.parametrize("shape, expected", [
    ("schema_violation_stop", "(stop_reason=STOP, response=nonempty)"),
    ("truncated_max_tokens", "(stop_reason=MAX_TOKENS, response=nonempty)"),
    ("parsed_is_a_dict", "(stop_reason=STOP, response=nonempty)"),
    ("empty_no_parts", "(stop_reason=SAFETY, response=empty)"),
    ("empty_no_candidates", "(stop_reason=unknown, response=empty)"),
    ("prohibited_content", "(stop_reason=PROHIBITED_CONTENT, response=empty)"),
    ("recitation_with_text", "(stop_reason=RECITATION, response=nonempty)"),
])
def test_the_refusal_message_is_exactly_this(shape, expected, refuse):
    """The before/after of the card, written out.

    BEFORE: ``extraction did not return a Statement: '{"bank": "ACMEPAYROLL
    BANK NA", "account_number": "4471009238", "beginning_balance": 118432.19,
    …'`` — 300 characters of the statement.
    AFTER:  the line below, which still tells the operator whether the model
    was cut off, blocked, or simply answered with the wrong shape.
    """
    assert str(refuse(shape)) == f"extraction did not return a Statement {expected}"


# --- the finding the card did not name --------------------------------------

@pytest.mark.parametrize("shape", ["empty_no_parts", "empty_no_candidates",
                                   "prohibited_content"])
def test_the_empty_response_half_now_raises_the_error_it_documents(shape, refuse):
    """The branch is commented "schema violation / empty response", and on the
    empty half it never delivered.

    `resp.text` is None whenever the response has no text part — a safety
    block, a blocked prompt, no candidates at all — and the old message
    subscripted it, so `None[:300]` raised
    `TypeError: 'NoneType' object is not subscriptable` from inside the raise
    statement. The RuntimeError this branch documents was never constructed,
    and every consumer that files `type(e).__name__` recorded a TypeError for
    what is actually a blocked response. Measured on the base tree, three of
    the seven shapes above.
    """
    exc = refuse(shape)
    assert type(exc) is RuntimeError, f"{shape} raised {type(exc).__name__}"
    assert "subscriptable" not in str(exc)


# --- the vocabulary helpers, under hostile input ----------------------------

class _Exploding:
    """An object whose every attribute access raises — the shape a defensive
    `except` is written for and a test rarely exercises."""

    def __getattr__(self, name):
        raise RuntimeError(f"attribute access carrying {WORD} {DIGITS}")


class _FakeReason:
    """A finish reason whose `.name` is not in the SDK's enum."""

    name = f"{WORD}_{DIGITS}"


class _TextRaises:
    candidates = None

    @property
    def text(self):
        raise RuntimeError(f"body unreadable: {POISON}")


@pytest.mark.parametrize("reason", [
    None,
    f"{WORD}{DIGITS}",                       # a raw string from a newer API
    _FakeReason(),                           # an enum-shaped object with a foreign name
    ["STOP", DIGITS],                        # not even a scalar (unhashable)
    12345,
])
def test_stop_reason_degrades_to_unknown_rather_than_echoing(reason):
    """Anything the SDK's enum does not name is reported as `unknown`.

    Fail-closed by construction: an unrecognised value is exactly the case
    where we cannot prove it carries no document text, so it is never the value
    that gets printed.
    """
    got = ex._stop_reason(_StubReason(reason))
    assert got == ex._UNKNOWN_STOP_REASON, got
    assert got in {*ex._STOP_REASONS, ex._UNKNOWN_STOP_REASON}
    assert WORD not in got and DIGITS not in got


class _StubReason:
    """A response-shaped object carrying one arbitrary `finish_reason`."""

    def __init__(self, reason):
        self.candidates = [type("C", (), {"finish_reason": reason})()]


def test_stop_reason_is_unknown_when_the_response_itself_explodes():
    assert ex._stop_reason(_Exploding()) == ex._UNKNOWN_STOP_REASON


def test_response_state_is_unavailable_when_the_body_cannot_be_read():
    """`unavailable` is a third state, not a synonym for `empty`: "there was no
    text" and "we could not find out" are different bugs."""
    state = ex._response_state(_TextRaises())
    assert state == "unavailable"
    assert state in ex._RESPONSE_STATES


def test_response_state_reads_only_truthiness():
    assert ex._response_state(_response(text=POISON, finish_reason=types.FinishReason.STOP)) == "nonempty"
    assert ex._response_state(_response(text=None, finish_reason=types.FinishReason.STOP)) == "empty"


def test_a_helper_never_lets_an_exception_escape():
    """Both helpers are total. A refusal that crashed while explaining itself
    would replace a RuntimeError with whatever the crash was — which is the
    exact defect the old `resp.text[:300]` had."""
    assert ex._extraction_refusal(_Exploding()).args == (
        "extraction did not return a Statement (stop_reason=unknown, response=unavailable)",
    )


# --- the success path is untouched ------------------------------------------

def test_a_valid_statement_still_comes_back(monkeypatch):
    """Control flow preserved: the refusal branch is the only thing that moved."""
    stmt = Statement(bank="Test Bank", transactions=[])
    resp = _response(text='{"bank": "Test Bank"}', finish_reason=types.FinishReason.STOP,
                     parsed=stmt)
    client = _StubClient(resp)
    monkeypatch.setattr(ex, "_get_client", lambda settings: client)
    settings = ex.Settings(api_key="", model="stub-model", escalation_model="stub-model")
    assert ex.extract_statement(POISONED_MARKDOWN, settings=settings) is stmt
    assert client.models.calls == 1


def test_no_client_is_ever_built():
    """$0 vendor, structurally: these tests patch `_get_client`, so the module
    global stays None and no API key is ever read."""
    assert ex._client is None


# --- structural guards ------------------------------------------------------

def _module_ast() -> ast.Module:
    return ast.parse(pathlib.Path(ex.__file__).read_text(encoding="utf-8"))


def test_no_raise_in_the_module_says_anything_it_did_not_write_itself():
    """Every `raise` in `analysis/extract.py` is either the shared refusal
    constructor or a literal string.

    The dynamic sweep can only poison branches its inputs reach. This reads the
    source, so a refusal added on an unreached path — or the old
    `raise RuntimeError(f"...{resp.text[:300]!r}")` restored — fails here even
    though no input finds it. An f-string anywhere inside a `raise` is refused
    outright: it is the one construct that can smuggle a value into a message
    without looking like it.
    """
    offenders = []
    for node in ast.walk(_module_ast()):
        if not isinstance(node, ast.Raise):
            continue
        exc = node.exc
        interpolating = any(isinstance(n, ast.JoinedStr) for n in ast.walk(node))
        built_by_the_constructor = (
            isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name)
            and exc.func.id == "_extraction_refusal"
        )
        literal_only = (
            isinstance(exc, ast.Call)
            and all(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in exc.args)
            and not exc.keywords
        )
        if interpolating or not (built_by_the_constructor or literal_only):
            offenders.append(f"line {node.lineno}: {ast.unparse(node)}")
    assert not offenders, (
        "analysis/extract.py raises something it did not write itself, so the "
        "message is not provably free of the model's transcription:\n  "
        + "\n  ".join(offenders)
    )


def test_the_refusal_interpolates_only_the_vocabulary_helpers():
    """`_extraction_refusal` may fill its template from `_stop_reason` and
    `_response_state` and from nothing else.

    Read from the source rather than sampled from inputs: a third field added
    as `len(response.text)` — or as `response.text[:80]` — would be the leak
    this whole file exists to prevent, and no input sweep proves its absence.
    """
    fn = next(node for node in ast.walk(_module_ast())
              if isinstance(node, ast.FunctionDef) and node.name == "_extraction_refusal")
    called = {
        node.func.id for node in ast.walk(fn)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert called == {"RuntimeError", "_stop_reason", "_response_state"}, sorted(called)
    templates = {
        node.func.value.id for node in ast.walk(fn)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "format" and isinstance(node.func.value, ast.Name)
    }
    assert templates == {"_REFUSAL"}, sorted(templates)
    assert not [n for n in ast.walk(fn) if isinstance(n, ast.JoinedStr)]


def test_the_vocabulary_helpers_return_only_closed_values():
    """`_stop_reason` and `_response_state` return constants or a value already
    tested for membership in a module-level vocabulary.

    The dynamic tests above cover the inputs anyone thought of; this covers the
    shape. A `return name` that lost its `if name in _STOP_REASONS` guard would
    pass every input test that happens to use a real enum member.
    """
    tree = _module_ast()
    for name, vocabulary in (("_stop_reason", "_STOP_REASONS"),
                             ("_response_state", "_RESPONSE_STATES")):
        fn = next(node for node in ast.walk(tree)
                  if isinstance(node, ast.FunctionDef) and node.name == name)
        guarded = {
            n.id for node in ast.walk(fn) if isinstance(node, ast.Compare)
            and any(isinstance(op, ast.In) for op in node.ops)
            and any(isinstance(c, ast.Name) and c.id == vocabulary for c in node.comparators)
            for n in ast.walk(node.left) if isinstance(n, ast.Name)
        }
        for node in ast.walk(fn):
            if not isinstance(node, ast.Return) or node.value is None:
                continue
            value = node.value
            if isinstance(value, ast.IfExp):        # `A if cond else B`
                candidates = [value.body, value.orelse]
            else:
                candidates = [value]
            for candidate in candidates:
                if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str):
                    continue
                assert isinstance(candidate, ast.Name), (
                    f"{name} returns {ast.unparse(candidate)}, which is neither a "
                    "literal nor a vocabulary-checked name")
                assert candidate.id in guarded | {"_UNKNOWN_STOP_REASON"}, (
                    f"{name} returns `{candidate.id}` without testing it against "
                    f"{vocabulary} first")


def test_the_module_reads_the_response_body_in_exactly_one_place():
    """`response.text` / `resp.text` may be touched only inside
    `_response_state`.

    The old message read it at the raise site; this keeps the transcription
    from acquiring a second reader — including one that only means to measure
    it — and it is the guard that would fail first if someone re-added a
    length or a preview.
    """
    tree = _module_ast()
    readers = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Attribute) and inner.attr == "text":
                readers.append((node.name, inner.lineno))
    assert {name for name, _ in readers} <= {"_response_state"}, readers

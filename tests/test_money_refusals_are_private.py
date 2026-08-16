"""THE EXCEPTION BOUNDARY, PROVEN AT THE GRAMMAR (W3 §MONEY-PRIVACY).

`analysis/money.py` is the layer that holds the printed cell. When it refuses
one, the refusal becomes a `ValueError` that travels: out of the parser, out of
`analyze_markdown`, and — via `webapp/worker.py`'s `str(exc)` — into the
durable job store and onto a screen. The law batch 4 wrote for `read_money`
(§MG-C2 D1) is that such a message names the reader and the refusal CLASS and
never echoes the statement. Batch 6 extends it to the rest of the module, where
five raising parsers spelled their refusal `ValueError(value)` — the cell,
verbatim — and three more inherited `float`'s
``could not convert string to float: '<the cell>'`` without spelling anything
at all.

WHAT THIS FILE ASSERTS, and why in this shape:

* it is driven by ``money.__all__``, not by a hand-list of the five functions
  the card named. A privacy law is a property of the whole exported surface;
  a hand-list proves only the members someone remembered, and the next reader
  added to this module would not be in it. `test_every_exported_callable_is_swept`
  fails the build if the invocation table below stops covering the exports.
* it poisons the token with canaries that cannot occur in a legitimate refusal
  message, then looks for them in three places — ``str(exc)``, the whole
  ``__cause__``/``__context__`` chain, and a rendered traceback. The chain
  matters because ``raise ... from exc`` passes a ``str()`` test and fails a
  traceback test, which is the exact shape the pre-batch-6 code had.
* it asserts on digit RUNS as well as the canaries, because the dangerous
  fragment of a leaked cell is not the word around it: it is the account
  number, the balance, the amount.
* `test_no_raise_in_the_module_names_anything_but_the_refusal_constructor`
  reads the module's own AST. The dynamic sweep can only poison the branches it
  reaches; the AST guard covers the ones it does not, and it is what fails if a
  future edit writes `raise ValueError(value)` on a path no test input hits.
"""
from __future__ import annotations

import ast
import inspect
import pathlib
import re
import traceback

import pytest

import analysis.money as m

# --- the poison -------------------------------------------------------------
#
# Two canaries, because a leak has two shapes. WORD is what a description
# column holds; DIGITS is account-shaped, which is the fragment that actually
# matters and the one a "the message is short now" fix would still leak.
WORD = "ACMEPAYROLL"
DIGITS = "4471009238"
EMDASH = "—"

#: Tokens engineered to reach a different refusal branch each. Named for the
#: branch, so a failure says which one leaked.
POISONED_TOKENS = {
    # no digits at all -> the conversion refuses (Decimal/float cannot read it)
    "conversion_wordy": WORD,
    # a digit run past MAX_INTEGER_DIGITS -> the digit-bound guard refuses
    "bound_account_shaped": f"{DIGITS}{DIGITS} {WORD}",
    # money-shaped but welded to text -> the conversion refuses
    "conversion_welded": f"{WORD}1,234.56",
    # two decimal points -> the conversion refuses, and this is the one shape
    # that reaches `parse_digit_scrubbed`'s inherited `float` raise
    "conversion_two_dots": f"{WORD}.1.2",
    # MG-D's widened case: the em dash is not a sign, so the token survives
    # into `parse_decimal` and is declined there (W3 §MGD10 finding 6)
    "emdash_sign": f"{EMDASH}${DIGITS}.56",
    # FR-CA spacing and comma decimal, poisoned
    "conversion_french": f"1 234,56 {WORD} {DIGITS}",
}

#: Every exported callable, with the arguments that make it read one token.
#: `test_every_exported_callable_is_swept` keeps this honest against
#: `money.__all__`.
INVOCATIONS = {
    "parse_amount": [
        ("parse_amount(STRICT_UNSIGNED)", lambda v: m.parse_amount(v, m.STRICT_UNSIGNED)),
        ("parse_amount(PARENS_OR_LEADING_MINUS)",
         lambda v: m.parse_amount(v, m.PARENS_OR_LEADING_MINUS)),
    ],
    "parse_money": [("parse_money", m.parse_money)],
    "parse_money_tokens": [("parse_money_tokens", m.parse_money_tokens)],
    "read_money": [("read_money", lambda v: m.read_money(v))],
    "parse_decimal": [("parse_decimal", m.parse_decimal)],
    "parse_signed_decimal": [("parse_signed_decimal", m.parse_signed_decimal)],
    "parse_decimal_mixed_separator": [
        ("parse_decimal_mixed_separator", m.parse_decimal_mixed_separator),
        ("parse_decimal_mixed_separator(single_comma_only)",
         lambda v: m.parse_decimal_mixed_separator(v, single_comma_only=True)),
    ],
    "parse_grouped_float": [("parse_grouped_float", m.parse_grouped_float)],
    "parse_trailing_minus_dropped": [
        ("parse_trailing_minus_dropped", m.parse_trailing_minus_dropped)
    ],
    "parse_french_amount": [
        ("parse_french_amount", m.parse_french_amount),
        ("parse_french_amount(parens)", lambda v: m.parse_french_amount(v, parens=True)),
    ],
    "parse_digit_scrubbed": [
        ("parse_digit_scrubbed", m.parse_digit_scrubbed),
        ("parse_digit_scrubbed(all markers)",
         lambda v: m.parse_digit_scrubbed(
             v, parens=True, leading_minus=True, trailing_minus=True)),
    ],
    "parse_digit_scrubbed_guarded": [],   # covered above; guard is the caller's
    "normalize_sign_glyphs": [("normalize_sign_glyphs", m.normalize_sign_glyphs)],
    "pad_leading_decimal": [("pad_leading_decimal", m.pad_leading_decimal)],
    "strip_currency": [("strip_currency", m.strip_currency)],
}

CASES = [
    (f"{reader}::{shape}", call, token)
    for entries in INVOCATIONS.values()
    for reader, call in entries
    for shape, token in POISONED_TOKENS.items()
]


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


def _fragments(token: str) -> list[str]:
    """The pieces of `token` whose appearance would be a leak.

    Digit runs of three or more: the refusal vocabulary's only number is the
    two-digit ``13`` of the digit-bound message, so three is the shortest run
    that cannot be a false positive.
    """
    return [WORD, DIGITS, token, token.strip(), *re.findall(r"\d{3,}", token)]


@pytest.mark.parametrize("label, call, token", CASES, ids=[c[0] for c in CASES])
def test_a_refusal_never_carries_the_token(label, call, token):
    """THE CARD. Feed a poisoned cell to every exported reader; whatever comes
    back, no fragment of the cell may be in it."""
    try:
        call(token)
    except Exception as exc:                                   # noqa: BLE001
        rendered = _rendered(exc)
        leaked = [f for f in _fragments(token) if f in rendered]
        assert not leaked, (
            f"{label} leaked {leaked!r} into its refusal:\n{rendered}"
        )


@pytest.mark.parametrize("label, call, token", CASES, ids=[c[0] for c in CASES])
def test_a_refusal_carries_no_chained_exception_at_all(label, call, token):
    """The chain is severed, not suppressed.

    `float`'s ValueError quotes its argument, so a refusal raised with
    `from exc` — or raised from INSIDE the `except` that caught it, which
    attaches `__context__` implicitly — passes a `str(exc)` test and leaks the
    moment a traceback is rendered. Every refusal in `money.py` is raised from
    outside its handler for this reason, so both links are empty.
    """
    try:
        call(token)
    except Exception as exc:                                   # noqa: BLE001
        assert exc.__cause__ is None, f"{label}: refusal carries a __cause__"
        assert exc.__context__ is None, f"{label}: refusal carries a __context__"


@pytest.mark.parametrize("label, call, token", CASES, ids=[c[0] for c in CASES])
def test_a_refusal_is_a_value_error_in_the_named_vocabulary(label, call, token):
    """A refusal stays a `ValueError` (the family's documented contract, which
    parsers and the `_guarded` dispatch seam both rely on) and says the one
    thing it is allowed to say."""
    try:
        call(token)
    except Exception as exc:                                   # noqa: BLE001
        assert isinstance(exc, ValueError), f"{label}: {type(exc).__name__}"
        message = str(exc)
        assert message.startswith("money grammar refused a printed token ("), message
        reason, _, reader = message[:-1].partition("; reader=")
        assert reason.split("(", 1)[1] in {
            "no digits in the cell",
            f"integer run longer than the {m.MAX_INTEGER_DIGITS}-digit bound",
            "decimal places are neither two nor three",
            "not a money token",
        }, message
        assert reader.isidentifier(), message


# --- the exact messages, pinned ---------------------------------------------

@pytest.mark.parametrize("reader, call", [
    ("parse_decimal", m.parse_decimal),
    ("parse_grouped_float", m.parse_grouped_float),
    ("parse_trailing_minus_dropped", m.parse_trailing_minus_dropped),
    ("parse_french_amount", m.parse_french_amount),
    ("parse_decimal_mixed_separator", m.parse_decimal_mixed_separator),
])
def test_the_refusal_message_is_exactly_this(reader, call):
    """The before/after of the card, written out.

    BEFORE: ``ValueError("ACMEPAYROLL")`` — the cell.
    AFTER:  the line below — the reader and the shape, and nothing else.
    """
    with pytest.raises(ValueError) as excinfo:
        call(WORD)
    assert str(excinfo.value) == (
        f"money grammar refused a printed token (no digits in the cell; reader={reader})"
    )


def test_parse_signed_decimal_reports_the_reader_that_actually_refused():
    """`parse_signed_decimal` reads the sign and delegates the number, so the
    refusal is `parse_decimal`'s and says so.

    Deliberate, not an oversight: the message names the function that declined
    the token rather than the entry point, which is what a diagnosis follows.
    The privacy property is identical either way — this pins the choice so it
    is a decision rather than an accident.
    """
    with pytest.raises(ValueError) as excinfo:
        m.parse_signed_decimal(f"{EMDASH}$500.00")
    assert str(excinfo.value) == (
        "money grammar refused a printed token (not a money token; reader=parse_decimal)"
    )


def test_the_account_shaped_run_that_started_the_card_is_gone():
    """MGD-C1's own example. `parse_signed_decimal("—$500.00")` began raising
    when MG-D took the em dash out of the sign class; before batch 6 it raised
    `ValueError("— 500.00")`, carrying the figure to a user-visible job error.
    """
    for call in (m.parse_decimal, m.parse_grouped_float, m.parse_signed_decimal,
                 m.parse_french_amount, m.parse_trailing_minus_dropped,
                 m.parse_decimal_mixed_separator):
        with pytest.raises(ValueError) as excinfo:
            call(f"{EMDASH}$123456789012345.99")
        message = str(excinfo.value)
        assert "123456789012345" not in message
        assert not any(run in message for run in ("1234", "2345", "456", "99"))


# --- structural guards ------------------------------------------------------

def test_every_exported_callable_is_swept():
    """The sweep is only a family proof if the family is the export list.

    `money.__all__` also exports data (the `AmountFormat` constants, the glyph
    class, the bound), which is not callable and cannot raise; everything that
    IS callable must appear in `INVOCATIONS`.
    """
    exported = {
        name for name in m.__all__
        if callable(getattr(m, name)) and not inspect.isclass(getattr(m, name))
    }
    missing = exported - set(INVOCATIONS)
    assert not missing, (
        f"exported callables with no poisoned-token case: {sorted(missing)} — "
        "add them to INVOCATIONS or the privacy law is unproven for them"
    )


def test_no_raise_in_the_module_names_anything_but_the_refusal_constructor():
    """Every `raise` in `analysis/money.py` is `raise _refusal(...)`.

    The dynamic sweep above can only poison branches its inputs reach. This
    reads the source instead, so a refusal added on an unreached path — or an
    old one restored to `raise ValueError(value)` — fails here even though no
    input finds it. `_refusal` is the single constructor precisely so that
    this guard can be one line of intent rather than a message whitelist.
    """
    source = pathlib.Path(m.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise):
            continue
        exc = node.exc
        ok = (
            isinstance(exc, ast.Call)
            and isinstance(exc.func, ast.Name)
            and exc.func.id == "_refusal"
        )
        if not ok:
            offenders.append(f"line {node.lineno}: {ast.unparse(node)}")
    assert not offenders, (
        "analysis/money.py raises outside `_refusal`, so the message is not "
        "provably token-free:\n  " + "\n  ".join(offenders)
    )


def test_the_refusal_class_vocabulary_is_closed():
    """`_refusal_class` may only ever return one of four fixed strings.

    Read from the source rather than sampled from inputs: a fifth category
    added as an f-string would be the leak this whole file exists to prevent,
    and no input sweep can prove its absence.
    """
    tree = ast.parse(pathlib.Path(m.__file__).read_text(encoding="utf-8"))
    fn = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_refusal_class"
    )
    returned = [node.value for node in ast.walk(fn) if isinstance(node, ast.Return)]
    for value in returned:
        if isinstance(value, ast.Constant):
            continue
        # the one interpolation allowed: the digit bound, a module constant
        assert isinstance(value, ast.JoinedStr), ast.unparse(value)
        names = {
            n.id for part in value.values if isinstance(part, ast.FormattedValue)
            for n in ast.walk(part) if isinstance(n, ast.Name)
        }
        assert names == {"MAX_INTEGER_DIGITS"}, (
            f"_refusal_class interpolates {sorted(names)} into a reason string; "
            "only module constants may appear there, never the token"
        )

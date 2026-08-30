"""The extraction response schema is a PROMPT SURFACE, not documentation.

`analysis/extract.py` passes `Statement` as the extraction call's
`response_schema`, and pydantic publishes a model's DOCSTRING as its
JSON-schema `description` and every `Field(description=...)` as the field's.
So prose written on any model reachable from that schema is not a note to the
next implementer: it is text handed to a language model, in the one call this
platform makes about a document's own figures.

The L-1 stage-1 card found that the hard way — the design it was implementing
instructed a docstring on `Statement`, and the words went into a comment
instead. A comment is not a guard: the next reader can write a docstring
without ever seeing it, and the effect is invisible in every payload, every
replay and every byte comparison, because it changes what a MODEL is told and
nothing about what a parser computes.

These tests are that guard, and they cover the THREE models the schema reaches
rather than the one the discovery was about: `Statement` embeds `Transaction`
and `StatementDailyBalance`, and pydantic publishes their docstrings under
`$defs` in exactly the same way.

WHAT TO DO WHEN THE PIN FAILS. Ask which of the two happened.

* A DOCSTRING or a class-level description appeared — do not re-pin. Move the
  words to a comment. That is the defect these tests exist to catch.
* A FIELD was added, removed or renamed, or a field description was
  deliberately reworded — that is a real schema change, it changes what the
  extractor is told, and it belongs to whoever made it: re-pin the digest in
  the same commit, and say in the message what the model is now being told.

Nothing here calls a model, and nothing here costs anything: the schema is
built locally from the class.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from analysis.schema import Statement, StatementDailyBalance, Transaction

ROOT = Path(__file__).resolve().parents[1]

#: The models reachable from the extraction call's `response_schema`. A fourth
#: one would change the digest below, and `test_the_schema_reaches_exactly_the
#: _models_this_file_guards` names it rather than leaving the reader to diff a
#: hash.
PROMPT_SURFACE_MODELS = (Statement, Transaction, StatementDailyBalance)

#: `sha256` of `json.dumps(Statement.model_json_schema(), sort_keys=True,
#: ensure_ascii=False)`. The whole schema, so a field description moves it too
#: — the docstring is the sharpest edge of this surface and not the only one.
PINNED_SCHEMA_DIGEST = (
    "82b3f8c1f8ea4bdb6d2bb412edf55cc9240e4295e4fe2fc05ce661c2032c7c78"
)


def schema() -> dict:
    return Statement.model_json_schema()


def canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def test_the_extraction_call_still_passes_this_schema():
    """The pin is only worth having while `Statement` IS the response schema.

    Read from the source rather than assumed, so that switching the extraction
    to another model fails here — with a message saying to point the guard at
    the new one — instead of leaving these tests pinning a schema nothing
    sends.
    """
    tree = ast.parse((ROOT / "analysis" / "extract.py").read_text(encoding="utf-8"))
    schemas = [
        keyword.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "response_schema"
    ]
    assert schemas, "analysis/extract.py passes no response_schema; re-aim this guard"
    names = {getattr(value, "id", None) or getattr(value, "attr", None) for value in schemas}
    assert names == {"Statement"}, (
        f"the extraction response schema is now {sorted(names)}; point these "
        f"tests at it, because its docstrings are what the model will be told"
    )


@pytest.mark.parametrize("model", PROMPT_SURFACE_MODELS,
                         ids=lambda model: model.__name__)
def test_no_model_on_the_prompt_surface_carries_a_docstring(model):
    """The direct hazard, named per model so the failure says which one."""
    assert model.__doc__ is None, (
        f"{model.__name__} has a docstring, and pydantic publishes it to the "
        f"extraction model as the schema's `description`. Move the words to a "
        f"comment: prose about this class is for the next implementer, and the "
        f"schema is a prompt"
    )


def test_the_schema_carries_no_class_level_description_anywhere():
    """The same property read from the OUTPUT rather than from the classes.

    Two ways to state one rule, deliberately: a future pydantic that sourced a
    class description from somewhere other than `__doc__` would pass the test
    above and fail this one.
    """
    published = schema()
    assert "description" not in published, (
        "the extraction schema carries a class-level description; that text is "
        "sent to the model"
    )
    for name, definition in (published.get("$defs") or {}).items():
        assert "description" not in definition, (
            f"the nested model {name} carries a class-level description; that "
            f"text is sent to the model"
        )


def test_the_schema_reaches_exactly_the_models_this_file_guards():
    published = schema()
    reached = set(published.get("$defs") or {}) | {published.get("title")}
    assert reached == {model.__name__ for model in PROMPT_SURFACE_MODELS}, (
        f"the extraction schema now reaches {sorted(reached)}; add the new "
        f"model to PROMPT_SURFACE_MODELS, because its docstring would be sent "
        f"to the extractor too"
    )


def test_the_extraction_schema_is_pinned_byte_for_byte():
    """Every byte of what the extractor is told, in one digest.

    The docstring tests above name the sharpest edge; this one is the surface.
    A field description reworded, a field added, an enum widened — all of them
    change the instruction the model receives, and none of them changes a
    payload, a replay or a byte comparison, so nothing else in this repository
    would notice.
    """
    digest = hashlib.sha256(canonical(schema()).encode("utf-8")).hexdigest()
    assert digest == PINNED_SCHEMA_DIGEST, (
        "the extraction schema changed. If a DOCSTRING or class description "
        "appeared, do not re-pin — move the words to a comment. If a field or "
        "a field description changed deliberately, re-pin this digest in the "
        "same commit and say in the message what the extractor is now told"
    )

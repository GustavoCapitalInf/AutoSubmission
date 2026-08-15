# Agent Handoff - REPAIR-GUARD (raised by MG-C, W3 §MG-C2 D1)
Ocean reviews and merges; you never merge or push.
**PROTECTED MODULE: `analysis/pipeline.py` (MASTER_PLAN §4). Ocean review +
forensic audit required. The diff below is pinned — it is two hunks and it
should stay two hunks.**

# Why this exists

MG-C2 made a refused money token raise instead of publishing 0.00. That is the
right refusal, and it exposed a seam that was always there.

`apply_statement_repairs` (`analysis/pipeline.py:89`, called at `:542`) runs
the bank-specific summary repairs AFTER dispatch, and it is **not inside the
guarded seam**. Everything the registry itself calls goes through
`parser_registry._guarded`, which is explicit that a raised exception is
reduced to facts that are safe to keep:

```python
except Exception as exc:
    failures.append(ParserFailure(registration.id, stage, type(exc).__name__))
    return None
```

`ParserFailure`'s own docstring states the law:

> `exception` is the exception's CLASS NAME and nothing else. An exception
> message routinely quotes the fragment of the document that provoked it […]
> The message is not stored anywhere, not even locally.

A repair-stage exception bypasses all of that. It propagates out of
`analyze_markdown` as a bare exception, and `webapp/worker.py:321` does
`store.set_error(job_id, str(e))` — so the message lands in the durable job
store and in front of a user.

**MG-C already closed the leak at the source** (`money.read_money` names the
reader and the refusal CLASS, never the token; pinned by
`test_the_refusal_message_leaks_nothing_from_an_account_shaped_token`). This
card closes the SEAM, which is the part that generalises: any repair that
raises anything — `int()` on a mangled cell, a `KeyError` on a mis-shaped
grid — still escapes with its message today, and those messages quote the
document.

# The card

Wrap the repair call in the same guarded shape the registry uses. A repair
that raises means "this repair produced nothing", exactly as a crashing
`parse` does — the normalized statement stands, unrepaired, and the crash is
recorded as a class name.

## Hunk 1 — `analysis/pipeline.py:541-544`

```python
     if deterministic_stmt is not None:
-        stmt = apply_statement_repairs(
-            markdown, normalize_statement(deterministic_stmt), dispatch=dispatch
-        )
+        normalized = normalize_statement(deterministic_stmt)
+        # A repair that raises must not carry the document out of the
+        # pipeline. `webapp/worker.py` stores `str(exc)` as the job error, and
+        # an exception message routinely quotes the cell that provoked it —
+        # the same invariant `ParserFailure` states for the dispatch seam
+        # (H3_SCHEMA I1). A failed repair means the UNREPAIRED statement
+        # stands, which is what this branch produced before repairs existed.
+        # (W3 §MG-C2 D1 / §REPAIR-GUARD.)
+        try:
+            stmt = apply_statement_repairs(markdown, normalized, dispatch=dispatch)
+        except Exception as exc:
+            stmt = normalized
+            repair_failure = type(exc).__name__
```

## Hunk 2 — the integrity flag, in `assess_document_integrity`

A swallowed repair may not be silent: it is a REVIEW cause with a named class,
in the same family as `parser_exception` (`pipeline.py:348`).

```python
+    if repair_failure is not None:
+        flags.append("repair_exception")
+        notes.append("a bank-summary repair raised and was discarded")
```

`telemetry/record.py::classify_outcome` already routes any integrity flag to
`review`, so no change is needed there; add `repair_exception` to
`telemetry/diagnostics.py`'s known-flag list beside `parser_exception`.

# Proof floor

- A fixture whose repair raises: assert the statement is the UNREPAIRED one,
  the flag is present, the outcome is `review`, and **the message is nowhere in
  the payload** (assert the provoking token is absent from the whole
  serialized report).
- `analysis/adb.py` and the financial core carry a zero-line diff.
- Full archive sweep: byte-identical. MG-C measured **zero** repair-stage
  refusals over the 3,367 documents with a cached artifact, so this card
  should move nothing; if anything moves, it is a repair that was already
  crashing and being surfaced raw, and it must be named.
- Full default suite + corpus-marked slice + `python corpus_gate.py` GREEN
  106/3 + guards + conformance cross-product.

# Not in scope

Changing what any repair DOES. This card only decides what happens when one
raises.

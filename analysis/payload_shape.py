"""The published payload's SHAPE, and the one discipline every reader shares.

`analysis/serialization.py` publishes two shapes and exactly two:

* the ACCOUNT shape — today's payload, a top-level ``statement`` and its
  siblings — which RULE S guarantees for every document carrying one account;
* the DOCUMENT shape — ``document`` + ``accounts``, and deliberately **no**
  top-level ``statement`` — for a document carrying more than one.

This module is not a reader. It publishes nothing, computes nothing about a
statement, and reads no value a document printed: it answers *which of the two
shapes is this, and may this reader answer about it at all*. It lives here, as
a leaf with no `analysis` import of its own, because the module that PUBLISHES
a shape is the one that should define the predicate for it — and because
`analysis/revenue.py` is itself one of the readers, which rules out
`serialization.py` as the home (it imports revenue, and a cycle would be the
price).

WHY A SHARED PREDICATE RATHER THAN A CHECK PER READER
-----------------------------------------------------
Measured, before any of this existed (`tools/l1_design_reader_probe.py`, and
§1.4 of the design): of the ten payload readers in the tree, **nine ANSWERED**
a document-shaped payload and one raised — and the one that raised did so only
because it indexed ``payload["statement"]`` where the others ``.get()`` it.
The loudness was an accident of punctuation, not a guard. Each of the nine
answered with a wrong answer of its own kind: an outcome of ``withheld`` naming
a check nobody ran, an empty diagnosis marked ``evaluated=True``, a revenue
view rebuilt over an empty ledger, an export with no rows. **The untaught
failure is quiet.** A reader that must not guess needs a refusal it cannot
forget to write, which is what the three entry points below are.

THE ASSERTION (L1-C16)
----------------------
* A payload carrying ``accounts`` may never also carry ``statement``. That
  combination is the Option-D shim the design refuses on evidence: it makes
  every untaught reader answer, and answer about ONE account of several,
  silently, on every surface, forever.
* A payload carrying NEITHER is not a document with nothing to say; it is a
  publisher defect, and a reader that folds it into an empty answer is how the
  defect stays invisible.

Both raise `PayloadShapeError`, which IS a `ValueError` — the design's word,
and what every caller that already narrows on `ValueError` will catch — with a
type of its own so a shape refusal can be told from a value refusal.

WHAT IS DARK AND WHY IT STAYS DARK
----------------------------------
Nothing in production builds a document payload at this tree:
`analysis/pipeline.py::analyze_document` publishes exactly one account on every
document, so `document_report_to_dict` takes its RULE S branch every time and
`ACCOUNTS_KEY` never appears in a published payload. Every branch these helpers
open is therefore unreachable in production until the stage that establishes a
second account from printed evidence lands — which is the point of teaching the
surfaces first. `refuse_document_payload` is written to make that provable: it
fires on the presence of ``accounts`` and on nothing else, so a reader that
gains it cannot change its answer to any payload the tree can currently
produce.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

#: The document block of the multi-account shape — facts about the DOCUMENT.
DOCUMENT_KEY = "document"
#: The account list, in PRINTED ORDER, one of today's payloads each.
ACCOUNTS_KEY = "accounts"
#: The single account's statement block — today's payload's root.
STATEMENT_KEY = "statement"

ACCOUNT_SHAPE = "account"
DOCUMENT_SHAPE = "document"


class PayloadShapeError(ValueError):
    """A payload whose shape a reader may not guess at.

    A `ValueError` on purpose: the design says the taught readers raise one,
    every caller that already narrows on `ValueError` keeps working, and the
    distinct type lets a shape refusal be told apart from a value refusal in a
    test without matching on message text.
    """


def is_document_payload(payload: object) -> bool:
    """Is this the multi-account shape? The presence of ``accounts``, and that alone.

    Deliberately not "does it lack ``statement``": a reader asks this question
    to decide whether to take a branch, and a predicate that could answer True
    for a merely malformed account payload would let a malformed payload reach
    the document branch. The malformed cases are the assertion's business.
    """
    return isinstance(payload, Mapping) and ACCOUNTS_KEY in payload


def assert_payload_shape(payload: object, *, surface: str) -> str:
    """`"account"` or `"document"`, or raise. The L1-C16 assertion.

    `surface` names the reader for the message; it is a constant of ours and
    never anything read out of a document.
    """
    if not isinstance(payload, Mapping):
        raise PayloadShapeError(
            f"{surface}: a published payload is a mapping; got "
            f"{type(payload).__name__} (payload_not_a_mapping)"
        )
    has_accounts = ACCOUNTS_KEY in payload
    has_statement = STATEMENT_KEY in payload
    if has_accounts and has_statement:
        raise PayloadShapeError(
            f"{surface}: a payload carrying {ACCOUNTS_KEY!r} may not also carry "
            f"{STATEMENT_KEY!r} — a top-level statement beside an account list "
            f"is one account of several wearing the document's name, which is "
            f"the defect the document model exists to remove "
            f"(payload_carries_both_shapes)"
        )
    if has_accounts:
        return DOCUMENT_SHAPE
    if has_statement:
        return ACCOUNT_SHAPE
    raise PayloadShapeError(
        f"{surface}: a payload carrying neither {STATEMENT_KEY!r} nor "
        f"{ACCOUNTS_KEY!r} is not a document with nothing to say, it is a "
        f"publisher defect; refusing rather than folding it into an empty "
        f"answer (payload_carries_no_shape)"
    )


def refuse_document_payload(payload: object, *, surface: str) -> None:
    """The LOUD refusal for a reader whose answer is about ONE account.

    Fires on the presence of ``accounts`` and on nothing else, so a reader that
    gains this line answers every payload the tree can currently publish
    exactly as it did before — the property that makes the whole teaching stage
    provably dark.
    """
    if is_document_payload(payload):
        raise PayloadShapeError(
            f"{surface} answers about one ACCOUNT and was handed a document "
            f"carrying {len(payload.get(ACCOUNTS_KEY) or ())} of them; a "
            f"single answer here would be one account's, published under the "
            f"document's name (reader_is_account_scope)"
        )


def payload_accounts(payload: object, *, surface: str) -> list[Mapping]:
    """Every account of this payload, in PRINTED ORDER — one for today's shape.

    The account shape yields `[payload]`, which is what makes a reader taught
    through this helper behave identically on every document the tree publishes
    today: one iteration, over the same mapping it read before.
    """
    shape = assert_payload_shape(payload, surface=surface)
    if shape == ACCOUNT_SHAPE:
        return [payload]
    accounts = payload[ACCOUNTS_KEY]
    if isinstance(accounts, (str, bytes)) or not isinstance(accounts, Sequence):
        raise PayloadShapeError(
            f"{surface}: {ACCOUNTS_KEY!r} must be a list in printed order; got "
            f"{type(accounts).__name__} (accounts_not_a_list)"
        )
    if not accounts:
        raise PayloadShapeError(
            f"{surface}: a document payload with no account may not be read; "
            f"an empty container in front of a reader is answered, not refused "
            f"(document_publishes_no_account)"
        )
    for index, account in enumerate(accounts):
        if not isinstance(account, Mapping) or STATEMENT_KEY not in account:
            raise PayloadShapeError(
                f"{surface}: account {index} of the document is not an account "
                f"payload (account_is_not_an_account_payload)"
            )
    return list(accounts)


def payload_document_block(payload: object, *, surface: str) -> Mapping:
    """The document block — empty for the account shape, which has no document facts.

    An account payload does not carry document facts and never gains them: the
    empty mapping is the truthful answer, not a placeholder.
    """
    shape = assert_payload_shape(payload, surface=surface)
    if shape == ACCOUNT_SHAPE:
        return {}
    block = payload.get(DOCUMENT_KEY)
    if not isinstance(block, Mapping):
        raise PayloadShapeError(
            f"{surface}: the document shape must carry a {DOCUMENT_KEY!r} block "
            f"(document_block_absent)"
        )
    return block


def payload_account_count(payload: object, *, surface: str) -> int:
    """How many accounts this payload publishes. One, for today's shape.

    The document block declares the count as well, and the two are checked
    against each other: a block that says three over a list of two is a
    publisher defect, and a reader that trusts either half of a contradiction
    is picking one at random.
    """
    accounts = payload_accounts(payload, surface=surface)
    block = payload_document_block(payload, surface=surface)
    declared = block.get("account_count") if block else None
    if declared is not None and declared != len(accounts):
        raise PayloadShapeError(
            f"{surface}: the document block declares {declared!r} account(s) "
            f"and the account list holds {len(accounts)} "
            f"(account_count_contradicts_the_list)"
        )
    return len(accounts)

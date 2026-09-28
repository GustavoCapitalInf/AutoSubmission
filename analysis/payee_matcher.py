"""The known-payee matcher (spec section 4.6, contract C3).

Every alias is normalized once and indexed by its tokens. An alias matches when its tokens appear
as consecutive whole tokens of the description, separated by single spaces. That is exactly the
boundary rule ``(?<![A-Z0-9])alias(?![A-Z0-9])`` the classifier has always applied, evaluated with
dictionary lookups instead of one regular-expression search per alias.

Registries are read-only after import. An index is built once per registry object and is not
rebuilt when that object is later mutated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Sequence

from .classification_registry import DEBT_RELIEF_ALIASES, PAYEE_GROUP_REGISTRIES
from .description_text import normalize_transaction_description

#: A spaced alias also matches its run-together form when that form has at least this many characters.
RUN_TOGETHER_MIN_LENGTH = 8
_TOKEN = re.compile(r"[A-Z0-9]+")
#: 5.3 (owner ruling 2026-09-27): a description token of letters with digits glued on (ADVANCE1234). Its letters
#: may stand for the LAST word of a multi-word alias whose last word is at least three letters, in the
#: known-payee index only.
_GLUED_DIGITS = re.compile(r"([A-Z]{3,})[0-9]+")


@dataclass(frozen=True)
class PayeeMatch:
    entity: str   # canonical entity
    state: str    # classification state from PAYEE_GROUP_REGISTRIES
    alias: str    # the alias as written in the registry


@dataclass(frozen=True)
class _Entry:
    length: int
    rank: int
    match: PayeeMatch


class AliasIndex:
    """Aliases normalized and compiled ONCE. match() returns the longest normalized alias found on token
    boundaries (?<![A-Z0-9])alias(?![A-Z0-9]); ties go to the earlier registry, then the earlier alias.
    A spaced alias whose run-together form has >= 8 characters also matches that form. With glued_digits, the
    last word of a multi-word alias whose last word has three letters or more also matches that word with digits
    glued on (5.3)."""

    def __init__(
        self,
        registries: Mapping[str, Mapping[str, Sequence[str]]],
        *,
        run_together: bool = True,
        glued_digits: bool = False,
    ) -> None:
        table: dict[tuple[str, ...], _Entry] = {}
        glued: dict[tuple[str, ...], _Entry] = {}
        joined: list[tuple[tuple[str, ...], _Entry]] = []
        rank = 0
        for state, registry in registries.items():
            for entity, aliases in registry.items():
                for alias in aliases:
                    normalized = normalize_transaction_description(alias)
                    if not normalized:
                        continue
                    tokens = tuple(normalized.split(" "))
                    entry = _Entry(len(normalized), rank, PayeeMatch(entity, state, alias))
                    rank += 1
                    table.setdefault(tokens, entry)
                    if glued_digits and len(tokens) > 1 and tokens[-1].isalpha() and len(tokens[-1]) >= 3:
                        glued.setdefault(tokens, entry)
                    form = "".join(tokens)
                    if run_together and len(tokens) > 1 and len(form) >= RUN_TOGETHER_MIN_LENGTH:
                        joined.append(((form,), _Entry(len(form), entry.rank, entry.match)))
        for tokens, entry in joined:
            table.setdefault(tokens, entry)
        self._table = table
        self._glued = glued
        self._longest = max((len(tokens) for tokens in table), default=0)

    def match(self, normalized_text: str) -> PayeeMatch | None:
        if not self._table or not normalized_text:
            return None
        runs = [(found.group(), found.start(), found.end()) for found in _TOKEN.finditer(normalized_text)]
        best: _Entry | None = None
        for start in range(len(runs)):
            tokens: list[str] = []
            for position in range(start, min(len(runs), start + self._longest)):
                if position > start and normalized_text[runs[position - 1][2]:runs[position][1]] != " ":
                    break
                tokens.append(runs[position][0])
                entry = self._table.get(tuple(tokens))
                if entry is None and self._glued and position > start:
                    split = _GLUED_DIGITS.fullmatch(tokens[-1])
                    if split is not None:
                        entry = self._glued.get((*tokens[:-1], split.group(1)))
                if entry is not None and (
                    best is None
                    or entry.length > best.length
                    or (entry.length == best.length and entry.rank < best.rank)
                ):
                    best = entry
        return None if best is None else best.match


_DEFAULT_INDEX = AliasIndex(PAYEE_GROUP_REGISTRIES, glued_digits=True)
#: 5.3 (owner ruling 2026-09-27): the debt-relief payees, an index of their own. They are read only after no known
#: payee matched, never as a longest-alias peer of the known-payee groups. Run-together forms are read (FORTHPAY,
#: RAMPAYMENTS), as in the known-payee index; registry_match never reads them.
_DEBT_RELIEF_INDEX = AliasIndex({"debt_relief": DEBT_RELIEF_ALIASES}, run_together=True)
_REGISTRY_INDEXES: dict[int, tuple[Mapping[str, Sequence[str]], AliasIndex]] = {}
_REGISTRY_INDEX_LIMIT = 64


def match_known_payee(normalized_text: str) -> PayeeMatch | None:
    """The longest alias across every group registry (spec section 4.6), or None."""
    return _DEFAULT_INDEX.match(normalized_text)


def match_debt_relief_payee(normalized_text: str) -> PayeeMatch | None:
    """5.3 (owner ruling 2026-09-27): the longest debt-relief alias (state "debt_relief"), or None."""
    return _DEBT_RELIEF_INDEX.match(normalized_text)


def registry_match(
    normalized_text: str,
    registry: Mapping[str, Sequence[str]],
) -> tuple[str, str] | None:
    """Same (canonical, alias) semantics as the classifier's original ``_registry_match``: the longest
    alias of one registry on token boundaries, ties to the earlier entity and alias, no run-together
    forms. The index is built once per registry object."""
    if not registry:
        return None
    cached = _REGISTRY_INDEXES.get(id(registry))
    if cached is None or cached[0] is not registry:
        if len(_REGISTRY_INDEXES) >= _REGISTRY_INDEX_LIMIT:
            _REGISTRY_INDEXES.clear()
        cached = (registry, AliasIndex({"": registry}, run_together=False))
        _REGISTRY_INDEXES[id(registry)] = cached
    found = cached[1].match(normalized_text)
    return None if found is None else (found.entity, found.alias)

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

from .classification_registry import (
    CREDIT_ONLY_ALIASES,
    DEBT_RELIEF_ALIASES,
    PAYEE_GROUP_REGISTRIES,
    REFERENCE_TIED_ALIASES,
)
from .description_text import normalize_transaction_description

#: A spaced alias also matches its run-together form when that form has at least this many characters.
RUN_TOGETHER_MIN_LENGTH = 8
_TOKEN = re.compile(r"[A-Z0-9]+")
#: 5.3 (owner ruling 2026-09-27): a description token of letters with digits glued on (ADVANCE1234). Its letters
#: may stand for the LAST word of a multi-word alias whose last word is at least three letters, in the
#: known-payee index only. Audit B6 (I08, I22): they may also stand for a whole run-together alias, one token of
#: RUN_TOGETHER_MIN_LENGTH letters or more (a one-word alias, or a multi-word alias's run-together form), in the
#: known-payee index a credit is read with only ('FORWARDFINUSA1', 'LCFGROUPINC7').
_GLUED_DIGITS = re.compile(r"([A-Z]{3,})[0-9]+")
#: Audit round 2, R2-B08 (R47 (b)): in the credit index only (run_together_digits), a whole run-together alias may also
#: carry one or two letters after its digit run ('FORWARDFINUSA1X', 'FORWARDFINUSA12AB'). Three letters or more are a
#: word and keep no reading (a documented limit).
_GLUED_DIGITS_LETTER_TAIL = re.compile(r"([A-Z]{3,})[0-9]+[A-Z]{1,2}")
#: Audit B6 (I24): the premium-finance lookup's glued-digit arm (registry_match(..., glued_digits=True)) reads a
#: one-word alias of this many letters or more with a digit run glued after it ('IPFS888' is IPFS).
REGISTRY_GLUED_MIN_LETTERS = 4
#: Audit B6 (I49): a reference code, the token a reference-tied alias must be followed by: letters and digits with at
#: least one digit.
_REFERENCE_CODE = re.compile(r"[A-Z0-9]*[0-9][A-Z0-9]*")


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
    #: Audit B6 (I49): the alias matches only where a reference code, or nothing, follows it (REFERENCE_TIED_ALIASES).
    tied: bool = False


class AliasIndex:
    """Aliases normalized and compiled ONCE. match() returns the longest normalized alias found on token
    boundaries (?<![A-Z0-9])alias(?![A-Z0-9]); ties go to the earlier registry, then the earlier alias.
    A spaced alias whose run-together form has >= 8 characters also matches that form. With glued_digits, the
    last word of a multi-word alias whose last word has three letters or more also matches that word with digits
    glued on (5.3). With run_together_digits (audit B6: I08, I22; the credit index), a run-together alias, one token of
    RUN_TOGETHER_MIN_LENGTH letters or more (a one-word alias or a multi-word alias's run-together form), also matches
    that token with digits glued on. `single_glued_min` (audit B6: I24) lets a one-word alias of that many letters or
    more match with digits glued on (the premium-finance lookup). An alias in `tied` (audit B6: I49) matches only where
    a reference code (a token with a digit) or nothing follows it, in its spaced and its run-together form; an alias in
    `excluded` (audit B6: the debit index leaves out CREDIT_ONLY_ALIASES) is not indexed. Audit round 2, R2-B08 (R47
    (b)): with run_together_digits, a single token that is no alias with digits glued on is read once more with one or
    two letters after its digit run (_GLUED_DIGITS_LETTER_TAIL), the same tied-alias rule applying; the premium-finance
    lookup's single_glued_min arm and the multi-word glued arm never read that tail."""

    def __init__(
        self,
        registries: Mapping[str, Mapping[str, Sequence[str]]],
        *,
        run_together: bool = True,
        glued_digits: bool = False,
        run_together_digits: bool = False,
        single_glued_min: int | None = None,
        tied: frozenset[str] = frozenset(),
        excluded: frozenset[str] = frozenset(),
    ) -> None:
        table: dict[tuple[str, ...], _Entry] = {}
        glued: dict[tuple[str, ...], _Entry] = {}
        single: dict[str, _Entry] = {}
        joined: list[tuple[tuple[str, ...], _Entry]] = []
        tied_forms = {normalize_transaction_description(alias) for alias in tied}
        excluded_forms = {normalize_transaction_description(alias) for alias in excluded}
        rank = 0
        for state, registry in registries.items():
            for entity, aliases in registry.items():
                for alias in aliases:
                    normalized = normalize_transaction_description(alias)
                    if not normalized or normalized in excluded_forms:
                        continue
                    tokens = tuple(normalized.split(" "))
                    entry = _Entry(len(normalized), rank, PayeeMatch(entity, state, alias), normalized in tied_forms)
                    rank += 1
                    table.setdefault(tokens, entry)
                    if glued_digits and len(tokens) > 1 and tokens[-1].isalpha() and len(tokens[-1]) >= 3:
                        glued.setdefault(tokens, entry)
                    one_word = len(tokens) == 1 and tokens[0].isalpha()
                    if run_together_digits and one_word and len(tokens[0]) >= RUN_TOGETHER_MIN_LENGTH:
                        single.setdefault(tokens[0], entry)
                    if single_glued_min is not None and one_word and len(tokens[0]) >= single_glued_min:
                        single.setdefault(tokens[0], entry)
                    form = "".join(tokens)
                    if run_together and len(tokens) > 1 and len(form) >= RUN_TOGETHER_MIN_LENGTH:
                        joined.append(((form,), _Entry(len(form), entry.rank, entry.match, entry.tied)))
        for tokens, entry in joined:
            table.setdefault(tokens, entry)
            if run_together_digits and tokens[0].isalpha():
                single.setdefault(tokens[0], entry)
        self._table = table
        self._glued = glued
        self._single = single
        self._letter_tail = run_together_digits
        self._longest = max((len(tokens) for tokens in table), default=0)
        #: Audit 2026-10-13 (F1, speed only): every proper prefix of an indexed alias's tokens. A window whose tokens
        #: are none of them grows into no alias: the table's and the glued arm's keys are table keys (the glued table
        #: is filled beside the table, from the same tokens), and the single and letter-tail arms read only a window's
        #: first token. tests/test_payee_matcher_speed.py holds the unpruned loop and answers every live index with it.
        self._prefixes = frozenset(tokens[:size] for tokens in table for size in range(1, len(tokens)))

    def match(self, normalized_text: str) -> PayeeMatch | None:
        if not self._table or not normalized_text:
            return None
        runs = [(found.group(), found.start(), found.end()) for found in _TOKEN.finditer(normalized_text)]
        best: _Entry | None = None
        # Audit 2026-10-13 (F1): each token's glued-digit split, read once per text (False: not read yet).
        splits: list[re.Match[str] | None | bool] = [False] * len(runs)
        for start in range(len(runs)):
            tokens: list[str] = []
            for position in range(start, min(len(runs), start + self._longest)):
                if position > start and normalized_text[runs[position - 1][2]:runs[position][1]] != " ":
                    break
                tokens.append(runs[position][0])
                window = tuple(tokens)
                entry = self._table.get(window)
                if entry is None and (self._glued or self._single):
                    split = splits[position]
                    if split is False:
                        split = splits[position] = _GLUED_DIGITS.fullmatch(tokens[-1])
                    if split is not None and position > start:
                        entry = self._glued.get((*tokens[:-1], split.group(1)))
                    elif split is not None:
                        entry = self._single.get(split.group(1))
                    elif self._letter_tail and position == start:
                        tail = _GLUED_DIGITS_LETTER_TAIL.fullmatch(tokens[-1])
                        if tail is not None:
                            entry = self._single.get(tail.group(1))
                if entry is not None and entry.tied and not _reference_follows(normalized_text, runs, position):
                    entry = None
                if entry is not None and (
                    best is None
                    or entry.length > best.length
                    or (entry.length == best.length and entry.rank < best.rank)
                ):
                    best = entry
                # Audit 2026-10-13 (F1): this window was read; no longer one can match (see _prefixes).
                if window not in self._prefixes:
                    break
        return None if best is None else best.match


def _reference_follows(normalized_text: str, runs: list[tuple[str, int, int]], position: int) -> bool:
    """Audit B6 (I49): the token after `position` is a reference code (_REFERENCE_CODE), or nothing follows."""
    if position + 1 >= len(runs):
        return True
    if normalized_text[runs[position][2]:runs[position + 1][1]] != " ":
        return False
    return _REFERENCE_CODE.fullmatch(runs[position + 1][0]) is not None


_DEFAULT_INDEX = AliasIndex(
    PAYEE_GROUP_REGISTRIES, glued_digits=True, tied=REFERENCE_TIED_ALIASES, excluded=CREDIT_ONLY_ALIASES,
)
#: Audit B6 (I08, I22): the known-payee index a credit is read with: the default index's aliases with the ledger's
#: CREDIT_ONLY_ALIASES, and a run-together alias with a digit run glued after it ('FORWARDFINUSA1'). A debit keeps the
#: default index: on debits these readings would add lender and flag readings the G7 allowlist has not signed off.
_CREDIT_INDEX = AliasIndex(
    PAYEE_GROUP_REGISTRIES, glued_digits=True, run_together_digits=True, tied=REFERENCE_TIED_ALIASES,
)
#: 5.3 (owner ruling 2026-09-27): the debt-relief payees, an index of their own. They are read only after no known
#: payee matched, never as a longest-alias peer of the known-payee groups. Run-together forms are read (FORTHPAY,
#: RAMPAYMENTS), as in the known-payee index; registry_match never reads them.
_DEBT_RELIEF_INDEX = AliasIndex({"debt_relief": DEBT_RELIEF_ALIASES}, run_together=True)
_REGISTRY_INDEXES: dict[tuple[int, bool], tuple[Mapping[str, Sequence[str]], AliasIndex]] = {}
_REGISTRY_INDEX_LIMIT = 64


def match_known_payee(normalized_text: str, *, credit: bool = False) -> PayeeMatch | None:
    """The longest alias across every group registry (spec section 4.6), or None. Audit B6 (I08, I22): a credit
    (`credit`) is read with the credit index (_CREDIT_INDEX)."""
    return (_CREDIT_INDEX if credit else _DEFAULT_INDEX).match(normalized_text)


def match_debt_relief_payee(normalized_text: str) -> PayeeMatch | None:
    """5.3 (owner ruling 2026-09-27): the longest debt-relief alias (state "debt_relief"), or None."""
    return _DEBT_RELIEF_INDEX.match(normalized_text)


def registry_match(
    normalized_text: str,
    registry: Mapping[str, Sequence[str]],
    *,
    glued_digits: bool = False,
) -> tuple[str, str] | None:
    """Same (canonical, alias) semantics as the classifier's original ``_registry_match``: the longest
    alias of one registry on token boundaries, ties to the earlier entity and alias, no run-together
    forms. The index is built once per registry object. Audit B6 (I24): with `glued_digits`, a one-word alias of
    REGISTRY_GLUED_MIN_LETTERS letters or more also matches with a digit run glued after it ('IPFS888')."""
    if not registry:
        return None
    key = (id(registry), glued_digits)
    cached = _REGISTRY_INDEXES.get(key)
    if cached is None or cached[0] is not registry:
        if len(_REGISTRY_INDEXES) >= _REGISTRY_INDEX_LIMIT:
            _REGISTRY_INDEXES.clear()
        single = REGISTRY_GLUED_MIN_LETTERS if glued_digits else None
        cached = (registry, AliasIndex({"": registry}, run_together=False, single_glued_min=single))
        _REGISTRY_INDEXES[key] = cached
    found = cached[1].match(normalized_text)
    return None if found is None else (found.entity, found.alias)

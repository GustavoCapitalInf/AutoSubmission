"""Audit 2026-10-13, F1: the alias matcher stops a window as soon as it can grow into no alias.

AliasIndex.match scanned every token window up to the longest alias's length from every start token, and re-ran the
glued-digit split on the same token for every window ending on it. A window whose tokens are not a proper prefix of
any indexed alias can grow into no alias: the table's keys and the glued arm's keys are table keys, and the single
and letter-tail arms read only a window's first token. So the matcher breaks there, after the window itself is read,
and reads each token's glued split once per text. The answers, their tie-breaking and the tied-alias rule are
unchanged.

The guard that makes the pruning safe to keep: `_reference_match` below is the loop as it stood before the change,
and every production index answers every alias of its own, in many shapes, and seeded random texts built from its
own tokens, with the very same object. A future lookup arm that reads a non-first token in a new way breaks it here
first. Fabricated text only (SAMPLE / CONTOSO / FABRIKAM / NORTHWIND), plus the registries' own aliases.
"""
from __future__ import annotations

import random
from collections.abc import Mapping, Sequence

import pytest

from analysis import classification_registry, payee_matcher
from analysis.transaction_classifier import statement
from analysis.description_text import normalize_transaction_description as normalize
from analysis.payee_matcher import AliasIndex
from tests.classifier_modules import classifier_modules


def _reference_match(index: AliasIndex, normalized_text: str):
    """AliasIndex.match as it stood before audit 2026-10-13 F1, verbatim in behaviour (no pruning)."""
    if not index._table or not normalized_text:
        return None
    runs = [(found.group(), found.start(), found.end()) for found in payee_matcher._TOKEN.finditer(normalized_text)]
    best = None
    for start in range(len(runs)):
        tokens: list[str] = []
        for position in range(start, min(len(runs), start + index._longest)):
            if position > start and normalized_text[runs[position - 1][2]:runs[position][1]] != " ":
                break
            tokens.append(runs[position][0])
            entry = index._table.get(tuple(tokens))
            if entry is None and (index._glued or index._single):
                split = payee_matcher._GLUED_DIGITS.fullmatch(tokens[-1])
                if split is not None and position > start:
                    entry = index._glued.get((*tokens[:-1], split.group(1)))
                elif split is not None:
                    entry = index._single.get(split.group(1))
                elif index._letter_tail and position == start:
                    tail = payee_matcher._GLUED_DIGITS_LETTER_TAIL.fullmatch(tokens[-1])
                    if tail is not None:
                        entry = index._single.get(tail.group(1))
            if entry is not None and entry.tied and not payee_matcher._reference_follows(normalized_text, runs, position):
                entry = None
            if entry is not None and (
                best is None
                or entry.length > best.length
                or (entry.length == best.length and entry.rank < best.rank)
            ):
                best = entry
    return None if best is None else best.match


def _is_registry(value: object) -> bool:
    return (
        isinstance(value, Mapping)
        and bool(value)
        and all(
            isinstance(key, str)
            and isinstance(aliases, Sequence)
            and not isinstance(aliases, str)
            and all(isinstance(alias, str) for alias in aliases)
            for key, aliases in value.items()
        )
    )


def _registries() -> list[Mapping[str, Sequence[str]]]:
    """Every registry the classifier and the true-revenue pass can hand registry_match: each module-level mapping of
    names to alias sequences, and each one nested one level down (the group and bank-specific registries)."""
    found: dict[int, Mapping[str, Sequence[str]]] = {}
    for module in (classification_registry, *classifier_modules()):
        for value in vars(module).values():
            if _is_registry(value):
                found.setdefault(id(value), value)
            elif isinstance(value, Mapping) and value and all(_is_registry(inner) for inner in value.values()):
                for inner in value.values():
                    found.setdefault(id(inner), inner)
    return list(found.values())


def _indexes() -> list[tuple[str, AliasIndex]]:
    indexes = [
        ("known_payee", payee_matcher._DEFAULT_INDEX),
        ("known_payee_credit", payee_matcher._CREDIT_INDEX),
        ("debt_relief", payee_matcher._DEBT_RELIEF_INDEX),
    ]
    for number, registry in enumerate(_registries()):
        for glued in (False, True):
            single = payee_matcher.REGISTRY_GLUED_MIN_LETTERS if glued else None
            indexes.append((
                f"registry{number}{'_glued' if glued else ''}",
                AliasIndex({"": registry}, run_together=False, single_glued_min=single),
            ))
    return indexes


INDEXES = _indexes()


def _alias_shapes(alias: str) -> list[str]:
    tokens = alias.split(" ")
    joined = "".join(tokens)
    shapes = [
        alias,
        f"SAMPLE {alias} 12345",
        f"PMT {alias}123",
        f"{alias}1X",
        f"{alias}12AB",
        f"{alias}123ABC",
        joined,
        f"{joined}77",
        f"{joined}7Q",
        f"{alias} REF12A34",
        f"{alias} CONTOSO",
        f"X{alias}",
        f"{alias} {alias}",
        f"{tokens[0]} {alias}",
        "  ".join(tokens),
        "-".join(tokens),
        "/".join(tokens),
    ]
    if len(tokens) > 1:
        shapes += [
            " ".join(tokens[:-1]),
            " ".join(tokens[1:]),
            f"{' '.join(tokens[:-1])} FABRIKAM {tokens[-1]}",
            f"{' '.join(tokens[:-1])} {tokens[-1]}9",
        ]
    return shapes


def _random_texts(index: AliasIndex, count: int, seed: int) -> list[str]:
    vocabulary = sorted({token for key in index._table for token in key}) or ["SAMPLE"]
    vocabulary += ["SAMPLE", "CONTOSO", "FABRIKAM", "NORTHWIND", "ACH", "REF12A34", "PMT"]
    chooser = random.Random(seed)
    texts = []
    for _ in range(count):
        parts = []
        for _ in range(chooser.randint(1, 9)):
            token = chooser.choice(vocabulary)
            roll = chooser.random()
            if roll < 0.15:
                token += str(chooser.randint(1, 9999))
            elif roll < 0.22:
                token += f"{chooser.randint(1, 99)}{chooser.choice(['X', 'AB', 'ABC'])}"
            parts.append(token)
        separators = [chooser.choice([" ", " ", " ", " ", "  ", "-", "/"]) for _ in parts[1:]]
        text = parts[0]
        for separator, part in zip(separators, parts[1:]):
            text += separator + part
        texts.append(text)
    return texts


@pytest.mark.parametrize("name, index", INDEXES, ids=[name for name, _ in INDEXES])
def test_every_alias_shape_and_random_text_answers_as_the_unpruned_loop(name, index):
    aliases = sorted({" ".join(key) for key in index._table})
    texts = [shape for alias in aliases for shape in _alias_shapes(alias)]
    texts += [normalize(text) for text in texts[::7]]
    texts += _random_texts(index, 1500, seed=sum(map(ord, name)))
    found = 0
    for text in texts:
        expected = _reference_match(index, text)
        assert index.match(text) is expected, (name, text)
        found += expected is not None
    # The sweep must reach the matches, not only the misses.
    assert found >= len(aliases)


def test_the_sweep_covers_every_live_index(monkeypatch):
    """Every registry a classification actually builds an index for is one the sweep above answers. (An empty index
    cache first: other tests install registries of their own.)"""
    from tools.bench_classifier import fabricated_statement

    monkeypatch.setattr(payee_matcher, "_REGISTRY_INDEXES", {})
    statement.classify_statement_readings(fabricated_statement(90))
    live = [registry for registry, _index in payee_matcher._REGISTRY_INDEXES.values()]
    swept = _registries()
    assert live
    assert all(any(candidate is registry for candidate in swept) for registry in live)
    for registry in (
        classification_registry.POTENTIAL_LENDER_ALIASES,
        classification_registry.PREMIUM_FINANCE_ALIASES,
        classification_registry.INSURANCE_PROVIDER_ALIASES,
        classification_registry.HEALTHCARE_PAYER_ALIASES,
    ):
        assert any(candidate is registry for candidate in swept)


class _CountingTable(dict):
    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.reads = 0

    def get(self, key, default=None):
        self.reads += 1
        return super().get(key, default)


def test_a_window_that_begins_no_alias_is_not_grown():
    """F1: with a three-token alias indexed, a four-token text none of whose tokens begins an alias is read in four
    window lookups, one per start token, not 3 + 3 + 2 + 1."""
    index = AliasIndex({"confirmed_lender": {"Contoso": ("CONTOSO SAMPLE PAYMENTS",)}})
    index._table = _CountingTable(index._table)

    assert index.match("FABRIKAM NORTHWIND WIDGET STORE") is None
    assert index._table.reads == 4


def test_a_window_that_begins_an_alias_still_grows_into_it():
    index = AliasIndex({"confirmed_lender": {"Contoso": ("CONTOSO SAMPLE PAYMENTS",)}})
    index._table = _CountingTable(index._table)

    found = index.match("ACH CONTOSO SAMPLE PAYMENTS NORTHWIND")

    assert found is not None and found.entity == "Contoso"
    # ACH; CONTOSO, CONTOSO SAMPLE, CONTOSO SAMPLE PAYMENTS; SAMPLE; PAYMENTS; NORTHWIND.
    assert index._table.reads == 7


def test_each_token_s_glued_split_is_read_once_per_text(monkeypatch):
    """F1: the glued-digit split of a token depends on the token alone, so it is read once per text, not once per
    window ending on it."""
    calls: list[str] = []
    real = payee_matcher._GLUED_DIGITS

    class _Counting:
        def fullmatch(self, text):
            calls.append(text)
            return real.fullmatch(text)

    monkeypatch.setattr(payee_matcher, "_GLUED_DIGITS", _Counting())
    index = AliasIndex(
        {"confirmed_lender": {"Contoso": ("CONTOSO SAMPLE PAYMENTS", "CONTOSO SAMPLE")}}, glued_digits=True,
    )

    index.match("CONTOSO SAMPLE PAYMENTS1234 NORTHWIND")

    # One read per token; the unpruned loop read eight (every window ending on a token the table missed).
    assert len(calls) == len(set(calls)) == 4

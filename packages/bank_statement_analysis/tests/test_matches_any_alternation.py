"""Audit 2026-10-13, F2: `_matches_any` searches one compiled alternation instead of one search per pattern.

`any(p.search(text) for p in patterns)` and `(?:p1)|(?:p2)|...` answer the same question (some pattern matches
somewhere) whenever the patterns are str patterns sharing one set of flags, with no backreference or conditional
group and no VERBOSE flag (a `#` comment would swallow the joined text). `_alternation` builds the alternation only
then, and keeps the loop for anything else. Pinned here:

* every module-level pattern tuple of the classifier and the true-revenue pass gets an alternation, except the one
  that holds duck-typed form objects, so a later edit cannot silently drop the speed-up;
* on witnesses generated from each pattern's own parse tree (one per branch choice, seeded) and fabricated
  descriptors, the alternation answers exactly as the loop, for every such tuple;
* the edge cases fall back to the loop: VERBOSE, bytes, mixed flags, a group reference, a list, a tuple holding
  something that is not a pattern, and an alternation that does not compile.
"""
from __future__ import annotations

import random
import re
import re._constants as sre
import re._parser as sre_parse

import pytest

from analysis.descriptor import rails
from analysis import description_text
from tests import zelle_setting_fixtures as fx
from tests.classifier_modules import classifier_modules
from tools.bench_classifier import fabricated_statement


def _loop(text, patterns) -> bool:
    return any(pattern.search(text) is not None for pattern in patterns)


def _collections() -> list[tuple[str, tuple]]:
    found: dict[int, tuple[str, tuple]] = {}
    for module in classifier_modules():
        for name, value in sorted(vars(module).items()):
            if isinstance(value, tuple) and value and any(isinstance(item, re.Pattern) for item in value):
                found.setdefault(id(value), (name, value))
    return sorted(found.values(), key=lambda item: item[0])


COLLECTIONS = _collections()
#: The tuples that keep the loop: the one that holds duck-typed form objects beside its patterns, and one whose two
#: patterns name the same group (one alternation does not compile; it is read pattern by pattern for that group, and
#: never passed to _matches_any).
LOOP_KEPT = {"_NON_REVENUE_CREDIT_PATTERNS", "_NAMED_DESIGNATION_TRANSFERS"}


_CATEGORY_SAMPLES = {
    sre.CATEGORY_DIGIT: "7", sre.CATEGORY_NOT_DIGIT: "Q", sre.CATEGORY_SPACE: " ", sre.CATEGORY_NOT_SPACE: "Q",
    sre.CATEGORY_WORD: "Q", sre.CATEGORY_NOT_WORD: " ",
}


def _class_sample(items, chooser: random.Random) -> str:
    if items and items[0][0] is sre.NEGATE:
        return chooser.choice(["Q", "7", " ", "#"])
    options: list[str] = []
    for op, value in items:
        if op is sre.LITERAL:
            options.append(chr(value))
        elif op is sre.RANGE:
            options.append(chr(chooser.randint(value[0], value[1])))
        elif op is sre.CATEGORY:
            options.append(_CATEGORY_SAMPLES.get(value, "Q"))
    return chooser.choice(options) if options else "Q"


def _witness(parsed, chooser: random.Random, depth: int = 0) -> str:
    """One string the parsed pattern may match: a seeded choice at every branch, repeat and class. Lookarounds and
    anchors are not satisfied on purpose: a witness need not match, the parity check only needs many that do."""
    out: list[str] = []
    for op, value in parsed:
        if op is sre.LITERAL:
            out.append(chr(value))
        elif op is sre.NOT_LITERAL:
            out.append("Q" if chr(value) != "Q" else "Z")
        elif op is sre.ANY:
            out.append("Q")
        elif op is sre.AT and value in (sre.AT_BOUNDARY, sre.AT_UNI_BOUNDARY):
            out.append(" ")
        elif op is sre.IN:
            out.append(_class_sample(value, chooser))
        elif op is sre.BRANCH:
            out.append(_witness(chooser.choice(value[1]), chooser, depth + 1))
        elif op in (sre.SUBPATTERN, sre.ATOMIC_GROUP):
            out.append(_witness(value[-1], chooser, depth + 1))
        elif op in (sre.MAX_REPEAT, sre.MIN_REPEAT, sre.POSSESSIVE_REPEAT):
            low, high, item = value
            high = low + 2 if high is sre.MAXREPEAT else high
            count = chooser.randint(low, max(low, min(high, low + 2)))
            out.append("".join(_witness(item, chooser, depth + 1) for _ in range(count)))
    return "".join(out)


def _witnesses(pattern: re.Pattern, count: int, seed: int) -> list[str]:
    try:
        parsed = sre_parse.parse(pattern.pattern, pattern.flags)
    except Exception:  # noqa: BLE001 - a pattern the generator cannot read is covered by the other texts
        return []
    chooser = random.Random(seed)
    return [_witness(parsed, chooser) for _ in range(count)]


def _fabricated_texts() -> list[str]:
    statements = [fabricated_statement(30)] + [fx.statement(rows) for rows, _holder, _title in fx.CASES.values()]
    texts = [description_text.normalize_transaction_description(t.description) for s in statements for t in s.transactions]
    return sorted(set(texts)) + ["", "SAMPLE", "CONTOSO NORTHWIND FABRIKAM", "ACH CREDIT SAMPLE PAYROLL 0001"]


FABRICATED_TEXTS = _fabricated_texts()


def test_the_census_found_the_rule_tuples():
    names = {name for name, _ in COLLECTIONS}
    assert len(COLLECTIONS) >= 60
    assert LOOP_KEPT <= names
    assert "_POS_PATTERNS" in names


@pytest.mark.parametrize("name, patterns", COLLECTIONS, ids=[name for name, _ in COLLECTIONS])
def test_every_rule_tuple_gets_its_alternation(name, patterns):
    combined = rails._alternation(patterns)
    if name in LOOP_KEPT:
        assert combined is None
    else:
        assert combined is not None, name
        assert rails._alternation(patterns) is combined


@pytest.mark.parametrize("name, patterns", COLLECTIONS, ids=[name for name, _ in COLLECTIONS])
def test_the_alternation_answers_as_the_loop(name, patterns):
    pool = random.Random(sum(map(ord, name)))
    own: list[str] = []
    for number, pattern in enumerate(item for item in patterns if isinstance(item, re.Pattern)):
        own += _witnesses(pattern, 6, seed=number + len(name))
    glued = [f"{pool.choice(own)} {pool.choice(own)}" for _ in range(min(60, len(own)))] if own else []
    framed = [f"SAMPLE {text} 0001" for text in own[::3]]
    others = [text for _other, collection in COLLECTIONS[::5] for item in collection[:2]
              if isinstance(item, re.Pattern) for text in _witnesses(item, 1, seed=7)]
    texts = own + glued + framed + others + FABRICATED_TEXTS
    positives = 0
    for text in texts:
        expected = _loop(text, patterns)
        assert rails._matches_any(text, patterns) is expected, (name, text)
        positives += expected
    assert positives > 0, name


def test_a_verbose_tuple_keeps_the_loop():
    """A `#` comment in a VERBOSE pattern would swallow the patterns joined after it."""
    patterns = (re.compile("A  # an A", re.X), re.compile("B\n|C", re.X))
    assert rails._alternation(patterns) is None
    assert rails._matches_any("B", patterns) is True
    assert rails._matches_any("D", patterns) is False


def test_a_bytes_tuple_keeps_the_loop():
    patterns = (re.compile(b"SAMPLE"), re.compile(b"CONTOSO"))
    assert rails._alternation(patterns) is None
    assert rails._matches_any(b"ACH CONTOSO", patterns) is True


@pytest.mark.parametrize(
    "patterns",
    [
        (re.compile("SAMPLE", re.I), re.compile("CONTOSO")),            # two sets of flags
        (re.compile(r"(A)\1"), re.compile("CONTOSO")),                   # a numbered group reference
        (re.compile(r"(?P<x>A)(?P=x)"), re.compile("CONTOSO")),          # a named group reference
        (re.compile(r"(?P<x>A)?(?(x)B|C)"), re.compile("CONTOSO")),      # a conditional group
        (re.compile(r"(?P<x>A)"), re.compile(r"(?P<x>B)")),              # a duplicate group name: does not compile
        (re.compile("SAMPLE"), "CONTOSO"),                               # not every member is a pattern
    ],
)
def test_a_tuple_the_alternation_cannot_answer_alike_keeps_the_loop(patterns):
    assert rails._alternation(patterns) is None
    for text in ("SAMPLE", "AA", "AB", "C", "B", "CONTOSO", "NORTHWIND"):
        if all(isinstance(pattern, re.Pattern) for pattern in patterns):
            assert rails._matches_any(text, patterns) is _loop(text, patterns)


def test_a_list_keeps_the_loop():
    patterns = [re.compile("SAMPLE"), re.compile("CONTOSO")]
    assert rails._alternation(patterns) is None
    assert rails._matches_any("ACH CONTOSO", patterns) is True


def test_a_tuple_built_per_call_never_grows_the_cache():
    for number in range(600):
        rails._matches_any("SAMPLE", (re.compile("SAMPLE"), re.compile(f"CONTOSO{number}")))
    assert len(rails._ALTERNATIONS) <= rails._ALTERNATION_LIMIT

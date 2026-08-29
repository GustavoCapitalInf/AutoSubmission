"""`fixpriv_ast_identity`: prose is invisible, behaviour is not.

The gate's whole value is that it answers NO when a "docstring-only" edit was
not one. Each test below pins one half of that: what it must call identical
(prose, in every place prose can sit) and what it must call different (any
string or value that is part of the tree, and any statement at all).

Nothing here reads the archive; the fixtures are invented shapes.
"""
from __future__ import annotations

import pytest

from tools.fixpriv_ast_identity import dump

BEFORE = '''
"""Module prose, the old wording.

    Beginning balance 26,245.24
"""
import re

PATTERN = re.compile(r"BOX 196\\s+OZARK, AR 72949")
EPSILON = 0.01


class Reader:
    """Class prose, the old wording — 1,326.43."""

    def read(self, text: str) -> float:
        """Function prose, the old wording — 7/02 1,647.77."""
        return float(text) + EPSILON
'''

#: The same module with EVERY docstring rewritten, lengthened and shortened,
#: and nothing else touched.
PROSE_ONLY = '''
"""Module prose, rewritten at greater length.

    Beginning balance 88,888.88
    and a second line the old one did not have
"""
import re

PATTERN = re.compile(r"BOX 196\\s+OZARK, AR 72949")
EPSILON = 0.01


class Reader:
    """Class prose, rewritten."""

    def read(self, text: str) -> float:
        """Function prose, rewritten — 7/02 8,888.88."""
        return float(text) + EPSILON
'''


def test_prose_only_edits_are_identical() -> None:
    assert dump(BEFORE) == dump(PROSE_ONLY)


def test_a_comment_is_invisible() -> None:
    assert dump(BEFORE) == dump(BEFORE.replace("import re", "import re  # a comment"))


def test_a_changed_regex_literal_is_a_difference() -> None:
    """A detection marker is behaviour, however much it looks like furniture."""
    after = BEFORE.replace("AR 72949", "AR 99999")
    assert dump(BEFORE) != dump(after)


def test_a_changed_numeric_constant_is_a_difference() -> None:
    assert dump(BEFORE) != dump(BEFORE.replace("EPSILON = 0.01", "EPSILON = 0.02"))


def test_a_changed_operator_is_a_difference() -> None:
    assert dump(BEFORE) != dump(BEFORE.replace("+ EPSILON", "- EPSILON"))


def test_a_renamed_symbol_is_a_difference() -> None:
    assert dump(BEFORE) != dump(BEFORE.replace("EPSILON", "TOLERANCE"))


def test_a_removed_statement_is_a_difference() -> None:
    assert dump(BEFORE) != dump(BEFORE.replace("import re\n", ""))


def test_a_string_that_is_not_a_docstring_is_part_of_the_tree() -> None:
    """Only the LEADING string of a body is prose; one below it is a statement."""
    before = "def f():\n    x = 1\n    'a note'\n    return x\n"
    after = "def f():\n    x = 1\n    return x\n"
    assert dump(before) != dump(after)


def test_a_docstring_only_body_survives_stripping() -> None:
    """A function whose body is nothing but prose must still parse and compare."""
    before = "def f():\n    'old prose'\n"
    after = "def f():\n    'new prose'\n"
    assert dump(before) == dump(after)
    assert dump(before) != dump("def f():\n    'old prose'\n    return 1\n")


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("x = 'literal'\n", "x = 'other'\n"),          # a module-level constant
        ("f('marker')\n", "f('other')\n"),             # an argument
        ("D = {'k': 'v'}\n", "D = {'k': 'w'}\n"),      # a mapping value
    ],
)
def test_every_other_string_position_is_behaviour(before: str, after: str) -> None:
    assert dump(before) != dump(after)

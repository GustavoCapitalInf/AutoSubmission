"""`fixpriv_ast_identity`: prose is invisible, behaviour is not.

The gate's whole value is that it answers NO when a "docstring-only" edit was
not one. Each test below pins one half of that: what it must call identical
(prose, in every place prose can sit) and what it must call different (any
string or value that is part of the tree, and any statement at all).

Nothing here reads the archive; the fixtures are invented shapes.
"""
from __future__ import annotations

import pytest

import subprocess

from tools.fixpriv_ast_identity import ROOT, dump, exists, main

BEFORE = '''
"""Module prose, the old wording.

    Beginning balance 777,777.77
"""
import re

PATTERN = re.compile(r"BOX 196\\s+OZARK, AR 99999")
EPSILON = 0.01


class Reader:
    """Class prose, the old wording — 818,181.81."""

    def read(self, text: str) -> float:
        """Function prose, the old wording — 7/02 909,090.91."""
        return float(text) + EPSILON
'''

#: The same module with EVERY docstring rewritten, lengthened and shortened,
#: and nothing else touched.
PROSE_ONLY = '''
"""Module prose, rewritten at greater length.

    Beginning balance 828,282.82
    and a second line the old one did not have
"""
import re

PATTERN = re.compile(r"BOX 196\\s+OZARK, AR 99999")
EPSILON = 0.01


class Reader:
    """Class prose, rewritten."""

    def read(self, text: str) -> float:
        """Function prose, rewritten — 7/02 838,383.83."""
        return float(text) + EPSILON
'''


def test_prose_only_edits_are_identical() -> None:
    assert dump(BEFORE) == dump(PROSE_ONLY)


def test_a_comment_is_invisible() -> None:
    assert dump(BEFORE) == dump(BEFORE.replace("import re", "import re  # a comment"))


def test_a_changed_regex_literal_is_a_difference() -> None:
    """A detection marker is behaviour, however much it looks like furniture."""
    after = BEFORE.replace("AR 99999", "AR 98989")
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


# --------------------------------------------------------------------------
# The bare invocation: the card's own method writes it, so it has to run.
# --------------------------------------------------------------------------

def _root_commit() -> str:
    out = subprocess.run(["git", "rev-list", "--max-parents=0", "HEAD"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return out.split()[-1]


def test_exists_tells_absence_from_failure() -> None:
    assert exists("HEAD", "tools/fixpriv_ast_identity.py")
    assert not exists("HEAD", "tools/a_file_this_tree_does_not_carry.py")


def test_a_path_absent_at_a_ref_is_skipped_and_counted(capsys) -> None:
    """With no paths the tool takes every `.py` that DIFFERS between the refs,
    which on a branch that adds a module includes files with no base version.
    There is no pair to compare, so the gate skips and says so. Treating that
    as a git failure exits 2 on the branch's own method line, and a gate that
    exits 2 on its own branch reads as broken to whoever runs it next."""
    code = main(["--base", _root_commit(), "--ref", "HEAD",
                 "tools/fixpriv_ast_identity.py"])
    printed = capsys.readouterr().out
    assert code == 0, printed
    assert "SKIPPED" in printed
    assert "skipped 1" in printed

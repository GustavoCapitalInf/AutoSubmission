"""The record redactor: it must not damage a sha, and it must be byte-minimal.

`cc64232` / `bbeeb5c` redacted the record with regex sweeps and shortened
content shas — the program's own names for its documents — which is how a
record stops being able to name what it is talking about. Every test here is
about the line-level operation, so none of them needs the archive: the residue
is passed in, which is also the point (the tool carries no token list).
"""
from __future__ import annotations

import pytest

from tools.fixpriv_w3_redact import REPLACEMENT, redact_line

SHA = "1B41B7B514AE699247E7CF668D7AB0236300F57F38CEC56C15027B35C4F26A85"
#: The record names most documents by a 16-character PREFIX of the sha, which is
#: the shortest thing the rule has to protect. This one carries a digit run long
#: enough to be scanned, which is the only way the test can be about anything.
SHA16 = "1B4123456789AE99"


def residue(**kwargs: set[str]) -> dict[str, set[str]]:
    base: dict[str, set[str]] = {"MONEY": set(), "DIGITS": set(), "DATES": set()}
    base.update(kwargs)
    return base


def test_a_money_figure_becomes_its_class() -> None:
    line = "the summary states 26,245.24 and closes\n"
    out, classes = redact_line(line, residue(MONEY={"26,245.24"}), 5)
    assert out == f"the summary states {REPLACEMENT['MONEY']} and closes\n"
    assert classes == ["MONEY"]


def test_a_figure_is_matched_with_or_without_its_separators() -> None:
    """The scanner records both forms of a money token; either may be printed."""
    out, _ = redact_line("total 26,245.24\n", residue(MONEY={"26245.24"}), 5)
    assert "26,245.24" not in out


def test_a_sha_is_never_cut() -> None:
    """A sha holds long digit runs; not one of them may be replaced."""
    line = f"| `{SHA}` | validated |\n"
    out, classes = redact_line(line, residue(DIGITS={"699247", "27035", "6300"}), 5)
    assert out == line
    assert classes == []


def test_a_sixteen_character_sha_prefix_is_still_protected() -> None:
    """The record names most documents by a 16-character prefix; that is a sha."""
    assert len(SHA16) == 16
    line = f"the mover `{SHA16}` moved\n"
    out, classes = redact_line(line, residue(DIGITS={"123456789", "23456"}), 5)
    assert out == line, "a digit run inside a 16-character sha prefix was replaced"
    assert classes == []


def test_a_number_beside_a_sha_is_still_redacted() -> None:
    line = f"`{SHA16}` account 8877665544 closed\n"
    out, classes = redact_line(line, residue(DIGITS={"8877665544"}), 5)
    assert SHA16 in out
    assert "8877665544" not in out
    assert classes == ["DIGITS"]


def test_nothing_outside_the_span_moves() -> None:
    """Byte-minimal: the line either side of the span is untouched, newline and all."""
    line = "  | `A1B2` | 1,234.56 | note, with commas |\r\n"
    out, _ = redact_line(line, residue(MONEY={"1,234.56"}), 5)
    assert out.startswith("  | `A1B2` | ")
    assert out.endswith(" | note, with commas |\r\n")


def test_a_line_with_no_residue_is_returned_unchanged() -> None:
    line = "validated 2,596 of 3,380 documents on 2026-08-29\n"
    out, classes = redact_line(line, residue(MONEY={"1,234.56"}), 5)
    assert out == line
    assert classes == []


def test_the_programs_own_counts_survive_because_they_are_not_residue() -> None:
    """Nothing is redacted for its shape alone; it must be in the residue."""
    line = "suite 6,742 passed; run 33195408456 concluded SUCCESS\n"
    out, classes = redact_line(line, residue(), 5)
    assert out == line
    assert classes == []


def test_a_digit_run_inside_a_money_figure_is_replaced_once() -> None:
    line = "balance 123456.78 today\n"
    out, classes = redact_line(line, residue(MONEY={"123456.78"}, DIGITS={"123456"}), 5)
    assert classes == ["MONEY"], "the widest span at a position wins"
    assert out.count("redacted") == 1


@pytest.mark.parametrize(
    ("cls", "token", "line"),
    [
        ("DATES", "04/30/2026", "the period ends 04/30/2026 as printed\n"),
        ("DATES", "April 30, 2026", "the period ends April 30, 2026 as printed\n"),
        ("DATES", "2026-04-30", "the period ends 2026-04-30 as printed\n"),
    ],
)
def test_every_date_notation_is_reached(cls: str, token: str, line: str) -> None:
    out, classes = redact_line(line, residue(DATES={token.upper()}), 5)
    assert classes == [cls]
    assert token not in out


def test_redaction_is_idempotent() -> None:
    line = "beginning 26,245.24 and account 8877665544 on 04/30/2026\n"
    res = residue(MONEY={"26,245.24"}, DIGITS={"8877665544"}, DATES={"04/30/2026"})
    once, first = redact_line(line, res, 5)
    twice, second = redact_line(once, res, 5)
    assert len(first) == 3
    assert second == []
    assert twice == once


def test_every_class_has_a_replacement() -> None:
    assert set(REPLACEMENT) == {"MONEY", "DIGITS", "DATES"}
    for marker in REPLACEMENT.values():
        assert marker.startswith("[") and marker.endswith("redacted]")

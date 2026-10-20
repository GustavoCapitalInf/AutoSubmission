"""The mutation harness must never leave a mutant in the working tree.

The re-review of FIXTURE-PRIVACY watched it happen: `git checkout --` died with
exit 255 — `index.lock` contention from another cell sharing this repository's
`.git` — inside the `finally` that was supposed to undo the mutant, so the
exception left the loop and the mutated scanner stayed on disk. Everything run
in that tree afterwards, in any worktree, would have been run against an
exclusion table with a hole punched in it on purpose.

These tests simulate that git failure rather than describing it. The harness's
own gates are mutated on a scratch file, git is replaced by a function that
raises the exit code that was actually seen, and the assertion is about the
BYTES on disk afterwards. A test named after a restore is not a test of one.
"""
from __future__ import annotations

import subprocess

import pytest

from tools import fixpriv_mutation_table as harness


LOCK_ERROR = (
    "fatal: Unable to create '<repo>/.git/index.lock': File exists.\n"
    "Another git process seems to be running in this repository.\n"
)


def _dead_git(*args: str) -> str:
    """git as this host produced it: `status` answers, `checkout` dies with 255."""
    if args and args[0] == "checkout":
        raise subprocess.CalledProcessError(255, args, "", LOCK_ERROR)
    return ""


def _silent_git(*args: str) -> str:
    """git that reports success and does nothing — the restore that is not one."""
    return ""


class _Shim:
    """`subprocess` as the harness sees it, so patching it reaches no further."""

    CalledProcessError = subprocess.CalledProcessError
    CompletedProcess = subprocess.CompletedProcess

    def __init__(self, run):
        self.run = run


def _gate(tmp_path, monkeypatch, *, original="VALUE = 1\n", mutant="VALUE = 2\n"):
    """One scratch gate file, one mutant over it, ROOT moved to the scratch."""
    path = tmp_path / "gate.py"
    path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(harness, "ROOT", tmp_path)
    monkeypatch.setattr(harness, "GATES", {"g": ("gate.py", "tests/scratch_suite.py")})
    monkeypatch.setattr(
        harness, "MUTANTS",
        (("X1", "g", "the value", "flip the value", original.strip(), mutant.strip()),),
    )
    monkeypatch.setattr(harness, "_GIT_BACKOFF", 0.0)
    return path


# --- the restore itself -------------------------------------------------


def test_the_restore_survives_the_git_failure_that_left_a_mutant_behind(tmp_path, monkeypatch):
    path = tmp_path / "gate.py"
    path.write_text("MUTATED\n", encoding="utf-8")
    monkeypatch.setattr(harness, "ROOT", tmp_path)
    monkeypatch.setattr(harness, "_git", _dead_git)
    monkeypatch.setattr(harness, "_GIT_BACKOFF", 0.0)

    harness._restore(path, "ORIGINAL\n")

    assert path.read_text(encoding="utf-8") == "ORIGINAL\n"


def test_the_restore_does_not_raise_when_git_raises(tmp_path, monkeypatch):
    path = tmp_path / "gate.py"
    path.write_text("MUTATED\n", encoding="utf-8")
    monkeypatch.setattr(harness, "ROOT", tmp_path)
    monkeypatch.setattr(harness, "_git", _dead_git)
    monkeypatch.setattr(harness, "_GIT_BACKOFF", 0.0)

    # No `pytest.raises`: the point is that nothing escapes, because this call
    # sits in a `finally` and an exception there abandons the mutant.
    harness._restore(path, "ORIGINAL\n")


def test_the_restore_does_not_believe_a_git_that_did_nothing(tmp_path, monkeypatch):
    """git reporting success is not evidence; the bytes are."""
    path = tmp_path / "gate.py"
    path.write_text("MUTATED\n", encoding="utf-8")
    monkeypatch.setattr(harness, "ROOT", tmp_path)
    monkeypatch.setattr(harness, "_git", _silent_git)
    monkeypatch.setattr(harness, "_GIT_BACKOFF", 0.0)

    harness._restore(path, "ORIGINAL\n")

    assert path.read_text(encoding="utf-8") == "ORIGINAL\n"


def test_the_restore_leaves_an_already_clean_file_alone(tmp_path, monkeypatch):
    path = tmp_path / "gate.py"
    path.write_text("ORIGINAL\n", encoding="utf-8")
    monkeypatch.setattr(harness, "ROOT", tmp_path)
    monkeypatch.setattr(harness, "_git", _silent_git)
    before = path.stat().st_mtime_ns

    harness._restore(path, "ORIGINAL\n")

    assert path.read_text(encoding="utf-8") == "ORIGINAL\n"
    assert path.stat().st_mtime_ns == before


# --- `_porcelain`: unknown is not clean ---------------------------------


def test_a_status_that_will_not_answer_is_none_and_not_an_empty_tree(monkeypatch):
    tries = []

    def refusing_git(*args: str) -> str:
        tries.append(args)
        raise subprocess.CalledProcessError(255, args, "", LOCK_ERROR)

    monkeypatch.setattr(harness, "_git", refusing_git)
    monkeypatch.setattr(harness, "_GIT_BACKOFF", 0.0)

    assert harness._porcelain() is None
    assert len(tries) == harness._GIT_TRIES


def test_a_status_that_answers_on_a_retry_is_believed(monkeypatch):
    answers = [subprocess.CalledProcessError(255, ("status",), "", LOCK_ERROR), "  \n"]

    def flaky_git(*args: str) -> str:
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(harness, "_git", flaky_git)
    monkeypatch.setattr(harness, "_GIT_BACKOFF", 0.0)

    assert harness._porcelain() == ""


# --- the run: refusals at both ends -------------------------------------


def test_the_run_refuses_to_start_on_a_dirty_tree(monkeypatch):
    monkeypatch.setattr(harness, "_porcelain", lambda: " M tools/privacy_scan_branch.py")
    assert harness.run(None) == 3


def test_the_run_refuses_to_start_when_git_will_not_say(monkeypatch):
    monkeypatch.setattr(harness, "_porcelain", lambda: None)
    assert harness.run(None) == 3


def test_the_run_refuses_to_report_when_the_tree_is_dirty_afterwards(tmp_path, monkeypatch, capsys):
    path = _gate(tmp_path, monkeypatch)
    answers = ["", " M something/else.py"]
    monkeypatch.setattr(harness, "_porcelain", lambda: answers.pop(0))
    monkeypatch.setattr(harness, "_git", _dead_git)
    monkeypatch.setattr(harness, "subprocess", _Shim(
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "FAILED tests/a.py::test_b\n", "")))

    assert harness.run(None) == 5
    assert "mutants" not in capsys.readouterr().out
    assert path.read_text(encoding="utf-8") == "VALUE = 1\n"


def test_the_run_refuses_to_report_when_a_gate_was_not_restored(tmp_path, monkeypatch, capsys):
    path = _gate(tmp_path, monkeypatch)
    monkeypatch.setattr(harness, "_porcelain", lambda: "")
    monkeypatch.setattr(harness, "_restore", lambda target, original: None)
    monkeypatch.setattr(harness, "subprocess", _Shim(
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "FAILED tests/a.py::test_b\n", "")))

    assert harness.run(None) == 4
    assert "mutants" not in capsys.readouterr().out
    # The harness said so rather than printing a table over a mutated tree.
    assert path.read_text(encoding="utf-8") == "VALUE = 2\n"


# --- the run, end to end, with git dead throughout ----------------------


def test_the_mutant_is_applied_and_then_restored_although_git_is_dead(tmp_path, monkeypatch):
    path = _gate(tmp_path, monkeypatch)
    monkeypatch.setattr(harness, "_porcelain", lambda: "")
    monkeypatch.setattr(harness, "_git", _dead_git)
    seen = {}

    def fake_suite(cmd, **kw):
        # What the suite would have been run against: the proof the mutant was
        # really applied, so a green table is not green by never mutating.
        seen["applied"] = path.read_text(encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 1, "FAILED tests/a.py::test_b\n", "")

    monkeypatch.setattr(harness, "subprocess", _Shim(fake_suite))

    assert harness.run(None) == 0
    assert seen["applied"] == "VALUE = 2\n"
    assert path.read_text(encoding="utf-8") == "VALUE = 1\n"


def test_a_survivor_is_reported_red_and_the_tree_is_still_restored(tmp_path, monkeypatch, capsys):
    path = _gate(tmp_path, monkeypatch)
    monkeypatch.setattr(harness, "_porcelain", lambda: "")
    monkeypatch.setattr(harness, "_git", _dead_git)
    monkeypatch.setattr(harness, "subprocess", _Shim(
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, "1 passed\n", "")))

    assert harness.run(None) == 1
    assert "SURVIVED" in capsys.readouterr().out
    assert path.read_text(encoding="utf-8") == "VALUE = 1\n"


def test_a_suite_that_cannot_be_launched_is_a_survivor_not_an_escape(tmp_path, monkeypatch, capsys):
    """The exception must not leave the loop: the restore and both checks follow it."""
    path = _gate(tmp_path, monkeypatch)
    monkeypatch.setattr(harness, "_porcelain", lambda: "")
    monkeypatch.setattr(harness, "_git", _dead_git)

    def cannot_launch(cmd, **kw):
        raise OSError("[WinError 8] Not enough memory resources are available")

    monkeypatch.setattr(harness, "subprocess", _Shim(cannot_launch))

    assert harness.run(None) == 1
    out = capsys.readouterr().out
    assert "NOT RUN" in out
    assert "survived 1" in out
    assert path.read_text(encoding="utf-8") == "VALUE = 1\n"


def test_a_mutant_whose_text_is_not_in_the_gate_is_a_survivor(tmp_path, monkeypatch, capsys):
    path = _gate(tmp_path, monkeypatch)
    monkeypatch.setattr(
        harness, "MUTANTS",
        (("X1", "g", "the value", "flip a value that is not there", "ABSENT", "PRESENT"),),
    )
    monkeypatch.setattr(harness, "_porcelain", lambda: "")
    monkeypatch.setattr(harness, "_git", _dead_git)
    monkeypatch.setattr(harness, "subprocess", _Shim(
        lambda cmd, **kw: pytest.fail("the suite must not run for a mutant that was not applied")))

    assert harness.run(None) == 1
    assert "NOT APPLIED" in capsys.readouterr().out
    assert path.read_text(encoding="utf-8") == "VALUE = 1\n"

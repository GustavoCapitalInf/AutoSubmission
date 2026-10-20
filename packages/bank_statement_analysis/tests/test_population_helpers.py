"""The population helpers `discovery.runner.read_population` and
`discovery.runner.holdout_sha16s_from_digest` (P22-TRUTHTABLE D7/D8).

Moved verbatim from `tests/test_research_mode.py` (model-code removal, slice
S5, plan D16) before that file left with the research mode: the two helpers
stay, deterministic and stdlib-only, because the text-first reader plan (AM-15)
is their planned caller, and the committed holdout digest is the one holdout
artefact runtime code may read. Added: `DEFAULT_HOLDOUT_DIGEST` moved beside
the reader and still names the committed digest.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from discovery.runner import DEFAULT_HOLDOUT_DIGEST, holdout_sha16s_from_digest, read_population

ROOT = Path(__file__).resolve().parents[1]


def test_read_population_accepts_comments_and_case_and_refuses_junk(tmp_path):
    path = tmp_path / "p.txt"
    path.write_text("# c\n" + "a" * 64 + "\n\n" + "B" * 64 + "  # trailing\n", encoding="utf-8")
    assert read_population(path) == frozenset({"A" * 64, "B" * 64})
    path.write_text("not-a-sha\n", encoding="utf-8")
    with pytest.raises(ValueError, match="population"):
        read_population(path)
    path.write_text("# only a comment\n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        read_population(path)


def test_the_holdout_digest_reader_reads_only_the_status_block(tmp_path):
    digest = tmp_path / "d.txt"
    digest.write_text(
        "# header\nstore_version: 1\nrecord_count: 2\nchain_head: GENESIS\nholdout_chain_head: GENESIS\n"
        "adjudicated_sha16:\n- AAAAAAAAAAAAAAAA\nholdout_sha16_status:\n- BBBBBBBBBBBBBBBB unseen\n"
        "- CCCCCCCCCCCCCCCC evaluated\n", encoding="utf-8")
    assert holdout_sha16s_from_digest(digest) == frozenset({"BBBBBBBBBBBBBBBB", "CCCCCCCCCCCCCCCC"})
    assert holdout_sha16s_from_digest(ROOT / "docs" / "moneythumb-replacement" / "truth" / "MANIFEST_DIGEST.txt") == frozenset()
    with pytest.raises(ValueError, match="digest"):
        holdout_sha16s_from_digest(tmp_path / "missing.txt")


def test_the_default_holdout_digest_is_the_committed_manifest_digest():
    """`DEFAULT_HOLDOUT_DIGEST` moved from `discovery/cli.py` to sit beside the
    reader (slice S5); the path it names is unchanged and the file exists."""
    assert DEFAULT_HOLDOUT_DIGEST == ROOT / "docs" / "moneythumb-replacement" / "truth" / "MANIFEST_DIGEST.txt"
    assert DEFAULT_HOLDOUT_DIGEST.is_file()
    assert holdout_sha16s_from_digest(DEFAULT_HOLDOUT_DIGEST) == frozenset()


def test_the_helpers_are_stdlib_only_and_offline():
    """They import nothing beyond what `discovery/runner.py` already imports at
    module level: the two functions read the standard library only (`re`,
    `pathlib`), which is what lets a later caller use them without a model or
    a cache."""
    import ast
    import inspect

    import discovery.runner as runner_module

    for function in (read_population, holdout_sha16s_from_digest):
        tree = ast.parse(inspect.getsource(function))
        assert not [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))], function
    assert runner_module.read_population is read_population

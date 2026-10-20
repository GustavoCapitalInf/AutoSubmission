"""`tools/hygiene8_base_tree.py` unpacks a base revision's `analysis/` with tarfile's `data` filter.

Python 3.12 and 3.13 warn (DeprecationWarning) on an `extractall` that names no filter, and an unfiltered unpack
writes wherever a member's name points; 3.14 made `data` the default. Naming it keeps the loader quiet and the
same on every interpreter CI and the development host run (3.12 and 3.14), and refuses a member that would leave
the scratch folder. The archive here is fabricated in memory and `git` is never run; the real loader is exercised
by the privacy comparisons (tests/test_raise_privacy3.py, tests/test_raise_privacy4.py).
"""
from __future__ import annotations

import io
import tarfile
import types
import warnings

import pytest

from tools import hygiene8_base_tree as base_tree
from tools.git_layout import PACKAGE_DIR

REVISION = "0" * 40


def _archive(members: list[tuple[str, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, data in members:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _fake_git(monkeypatch, archive: bytes) -> list[list[str]]:
    calls: list[list[str]] = []

    def run(argv, **kwargs):
        calls.append(list(argv))
        return types.SimpleNamespace(stdout=archive, returncode=0)

    monkeypatch.setattr(base_tree.subprocess, "run", run)
    return calls


FABRICATED_TREE = [("analysis/__init__.py", b""), ("analysis/money.py", b"ROUNDING = 2\n")]


def test_the_archive_is_unpacked_with_the_data_filter(tmp_path, monkeypatch):
    filters = []
    original = tarfile.TarFile.extractall

    def recording(self, *args, **kwargs):
        filters.append(kwargs.get("filter"))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(tarfile.TarFile, "extractall", recording)
    calls = _fake_git(monkeypatch, _archive(FABRICATED_TREE))
    base_tree._extract(REVISION, tmp_path / "out")
    assert calls == [["git", "cat-file", "-e", f"{REVISION}:./"],
                     ["git", "-C", str(PACKAGE_DIR), "archive", REVISION, "analysis"]]
    assert filters == ["data"]
    assert (tmp_path / "out" / "analysis" / "money.py").read_bytes() == b"ROUNDING = 2\n"


def test_unpacking_a_base_tree_warns_nothing(tmp_path, monkeypatch):
    _fake_git(monkeypatch, _archive(FABRICATED_TREE))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        base_tree._extract(REVISION, tmp_path / "out")
    assert sorted(path.name for path in (tmp_path / "out" / "analysis").iterdir()) == ["__init__.py", "money.py"]


def test_a_member_that_would_leave_the_scratch_folder_is_refused(tmp_path, monkeypatch):
    _fake_git(monkeypatch, _archive([("analysis/__init__.py", b""), ("../escape.py", b"PLANTED = 1\n")]))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)  # an unfiltered 3.12 unpack would warn, then write
        with pytest.raises(tarfile.FilterError):
            base_tree._extract(REVISION, tmp_path / "out")
    assert not (tmp_path / "escape.py").exists()

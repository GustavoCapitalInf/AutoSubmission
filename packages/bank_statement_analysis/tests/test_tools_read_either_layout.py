"""Research tools must see the same project on either side of the pure rename."""
from __future__ import annotations

import json
import sqlite3
import subprocess

import pytest

from tools.git_layout import PACKAGE_DIR, PACKAGE_PREFIX

PRE_MOVE = "8ccd1d46"
POST_MOVE = "ded21ce2"
DEFAULT_BASE = "10cc722"
SCHEMA_BASE = "223e21d0"
APPS_ADDED = "04c926de"


@pytest.fixture(autouse=True, scope="module")
def history():
    for ref in (PRE_MOVE, POST_MOVE, DEFAULT_BASE, SCHEMA_BASE, APPS_ADDED):
        proc = subprocess.run(
            ["git", "cat-file", "-e", f"{ref}^{{commit}}"],
            cwd=PACKAGE_DIR, capture_output=True,
        )
        if proc.returncode:
            pytest.skip(f"history does not contain {ref} (shallow clone)")
    renames = subprocess.run(
        ["git", "diff", "--name-status", "-M100%", PRE_MOVE, POST_MOVE],
        cwd=PACKAGE_DIR, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    assert renames and all(line.startswith("R100\t") for line in renames)


@pytest.fixture(autouse=True)
def from_the_package_folder(monkeypatch):
    monkeypatch.chdir(PACKAGE_DIR)


@pytest.fixture(params=["default", "diff.relative"])
def git_config(request, monkeypatch):
    if request.param == "diff.relative":
        monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
        monkeypatch.setenv("GIT_CONFIG_KEY_0", "diff.relative")
        monkeypatch.setenv("GIT_CONFIG_VALUE_0", "true")


def test_privacy_diff_has_the_same_sites_and_exclusions():
    from tools.privacy_scan_branch import added_lines, excluded_by

    before = added_lines(DEFAULT_BASE, PRE_MOVE)
    after = added_lines(DEFAULT_BASE, POST_MOVE)
    assert before
    assert sorted((path.removeprefix("../../"), number, text) for path, number, text in after) == sorted(before)
    dates = [(path, text) for path, _, text in after
             if path.startswith("docs/") and "2026-08-28" in text]
    assert dates
    assert all(excluded_by("DATES", path, "2026-08-28", text) == "docs_session_date"
               for path, text in dates)


@pytest.mark.usefixtures("git_config")
def test_privacy_diff_scans_files_outside_the_package():
    from tools.privacy_scan_branch import added_lines

    files = {path for path, _, _ in added_lines(PRE_MOVE, APPS_ADDED)}
    assert {"../../apps/auto_submission/README.md", "../../.github/workflows/corpus-gate.yml",
            "../../README.md", "README.md"} <= files


@pytest.mark.parametrize("finding", ["docs_date", "named_residue"])
def test_privacy_tree_keeps_path_classification(tmp_path, monkeypatch, capsys, finding):
    from telemetry import run_of_record
    from tools import privacy_scan_branch as scan

    source = subprocess.run(
        ["git", "show", f"{PRE_MOVE}:docs/adb-audit-results.csv"],
        cwd=PACKAGE_DIR, capture_output=True, text=True, check=True,
    ).stdout
    round_money = next(token for token in scan.MONEY_RE.findall(source) if token.endswith(".00"))
    with sqlite3.connect(tmp_path / "webapp.db"):
        pass
    monkeypatch.setattr(run_of_record, "partitions_for_run", lambda *a, **kw: None)
    monkeypatch.setattr(scan, "rows_by_sha", lambda run: {})
    monkeypatch.setattr(scan, "cached_text", lambda *a: f"{round_money} 2026-08-28")
    monkeypatch.setattr(scan, "tracked_text", lambda ref: "")
    reports = []
    for ref in (PRE_MOVE, POST_MOVE):
        out = tmp_path / f"{ref}.json"
        scan.main([
            "--data-dir", str(tmp_path), "--run", str(tmp_path), "--sha", "A" * 64,
            "--base", PRE_MOVE, "--ref", ref, "--include-tree", "--out", str(out),
        ])
        reports.append(json.loads(out.read_text()))
        capsys.readouterr()
    if finding == "docs_date":
        counts = [report["excluded_by_rule"]["docs_session_date"] for report in reports]
        assert counts[0] > 0
        assert counts[1] == counts[0]
    else:
        counts = [report["residue_by_named_class"]["benchmark_truth_csv"]
                  for report in reports]
        assert counts[0] > 0
        assert counts[1] == counts[0]
        hits = [hit for hit in reports[1]["hits"]
                if hit["file"] == "tree:docs/adb-audit-results.csv"
                and hit["class"] == "MONEY" and hit["token"] == round_money]
        assert hits
        assert all(hit["excluded_by"] is None for hit in hits)


@pytest.mark.usefixtures("git_config")
def test_train_stops_on_a_conflict_outside_the_package(monkeypatch, capsys):
    from tools import train_merge_one as train

    real_run = train.run

    def fabricated_merge(*args, check=True):
        if args[1] == "diff":
            historical = [arg.replace("--diff-filter=U", "--diff-filter=AMR") for arg in args]
            return real_run(*historical, DEFAULT_BASE, APPS_ADDED, "--",
                            f":(top){PACKAGE_PREFIX}{train.W3}", ":(top)apps")
        if args[1] == "merge-base":
            return subprocess.CompletedProcess(args, 0, PRE_MOVE.encode(), b"")
        assert args[1] == "merge"
        return subprocess.CompletedProcess(args, 1, b"", b"")

    monkeypatch.setattr(train, "run", fabricated_merge)
    assert train.main(["train_merge_one", APPS_ADDED, "fabricated"]) == 3
    output = capsys.readouterr().out
    assert "apps/auto_submission/README.md" in output
    assert "NON-W3 CONFLICT" in output


def test_train_reads_either_layout():
    from tools.train_merge_one import blob

    before = blob(PRE_MOVE)
    assert before
    assert blob(POST_MOVE) == before


def test_train_recognises_a_project_conflict(monkeypatch, capsys):
    from tools import train_merge_one as train

    real_run = train.run

    def fabricated_merge(*args, check=True):
        if args[1] == "diff":
            historical = [arg.replace("--diff-filter=U", "--diff-filter=AMR") for arg in args]
            return real_run(*historical, DEFAULT_BASE, POST_MOVE, "--", train.W3)
        if args[1] == "merge-base":
            return subprocess.CompletedProcess(args, 0, PRE_MOVE.encode(), b"")
        assert args[1] == "merge"
        return subprocess.CompletedProcess(args, 1, b"", b"")

    monkeypatch.setattr(train, "run", fabricated_merge)
    monkeypatch.setattr(train, "blob", lambda rev: {PRE_MOVE: b"base", "HEAD": b"ours",
                                                  POST_MOVE: b"changed"}[rev])
    assert train.main(["train_merge_one", POST_MOVE, "fabricated"]) == 4
    assert "W3 SHAPE VIOLATION" in capsys.readouterr().out
